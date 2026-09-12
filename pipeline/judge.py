import os
import json
import time
import requests
import mimetypes
from pipeline.config import GEMINI_FLASH, GEMINI_API_BASE
from pipeline.gemini import _clean_json_output, _shared_pool


RETRIABLE_STATUS_CODES = {400, 403, 429, 500, 502, 503, 504}


def _http_status(exc: Exception) -> int:
    response = getattr(exc, "response", None)
    return int(getattr(response, "status_code", 0) or 0)


_FAILED_JUDGE_KEYS = set()
_BANNED_KEY_SUFFIXES = ("pFGQ", "0YEw")  # Keys known to return 403 on Google Files API upload


def _is_valid_judge_key(k: str) -> bool:
    if not k:
        return False
    if k in _FAILED_JUDGE_KEYS:
        return False
    if any(k.endswith(suffix) for suffix in _BANNED_KEY_SUFFIXES):
        return False
    return True


def _get_judge_key(attempt: int = 0) -> str | None:
    global _FAILED_JUDGE_KEYS
    all_keys = []

    # Check dedicated judge env key first if not banned
    judge_env_key = os.environ.get("GEMINI_JUDGE_API_KEY", "").strip()
    if _is_valid_judge_key(judge_env_key):
        all_keys.append(judge_env_key)

    # Gather all valid keys from shared pool
    if hasattr(_shared_pool, "_keys"):
        for k in _shared_pool._keys:
            if _is_valid_judge_key(k) and k not in all_keys:
                all_keys.append(k)

    # Fallback to single GEMINI_API_KEY
    single_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if _is_valid_judge_key(single_key) and single_key not in all_keys:
        all_keys.append(single_key)

    if not all_keys:
        print("[JudgeAI] Warning: No valid judge keys available for Files API upload!")
        return None

    chosen_key = all_keys[attempt % len(all_keys)]
    slot = _shared_pool._keys.index(chosen_key) + 1 if (hasattr(_shared_pool, "_keys") and chosen_key in _shared_pool._keys) else "DEDICATED"
    print(f"[JudgeAI] Selected key slot {slot} for review attempt {attempt + 1}/{max(3, len(all_keys))}")
    return chosen_key

def upload_file_to_gemini(filepath: str, api_key: str) -> dict:
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type:
        mime_type = "video/mp4"
        
    file_size = os.path.getsize(filepath)
    filename = os.path.basename(filepath)
    
    upload_path = filepath
    temp_proxy = None
    if file_size > 18 * 1024 * 1024:
        temp_proxy = filepath.replace(".mp4", "_review_proxy.mp4")
        try:
            print(f"[JudgeAI] Video size ({file_size / (1024*1024):.1f} MB) exceeds 18MB. Encoding lightweight review proxy...")
            import subprocess
            subprocess.run([
                "ffmpeg", "-y", "-i", filepath,
                "-vf", "scale=-2:720", "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "64k", temp_proxy
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
            if os.path.exists(temp_proxy) and os.path.getsize(temp_proxy) > 1000:
                upload_path = temp_proxy
                file_size = os.path.getsize(upload_path)
                filename = os.path.basename(upload_path)
        except Exception as e:
            print(f"[JudgeAI] Proxy encoding warning: {e}. Falling back to original file.")
            temp_proxy = None

    print(f"Uploading file '{filename}' ({file_size / (1024*1024):.2f} MB) to Gemini Files API...")
    
    url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?uploadType=media&key={api_key}"
    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
    }
    
    try:
        for attempt in range(2):
            try:
                with open(upload_path, "rb") as f:
                    response = requests.post(url, headers=headers, data=f, timeout=45)
                if response.status_code == 403:
                    print(f"[JudgeAI] Upload returned 403 Forbidden. Rotating key immediately.")
                    raise requests.exceptions.HTTPError("403 Forbidden during upload", response=response)
                if response.status_code == 429:
                    from pipeline.gemini import _is_daily_quota_exhausted
                    if _is_daily_quota_exhausted(response):
                        print("[JudgeAI] Upload call daily quota exhausted. Rotating immediately.")
                        raise requests.exceptions.HTTPError("Daily quota exhausted during upload", response=response)
                    wait_s = (attempt + 1) * 5
                    print(f"[JudgeAI] Upload 429 rate limit. Retrying in {wait_s}s...")
                    time.sleep(wait_s)
                    continue
                if response.status_code in (500, 502, 503, 504):
                    wait_s = (attempt + 1) * 5
                    print(f"[JudgeAI] Upload {response.status_code} server error. Retrying in {wait_s}s...")
                    time.sleep(wait_s)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError:
                raise
            except requests.exceptions.RequestException as e:
                wait_s = (attempt + 1) * 5
                print(f"[JudgeAI] Upload network error: {e}. Retrying in {wait_s}s...")
                time.sleep(wait_s)
                
        raise RuntimeError("Failed to upload video file after retries.")
    finally:
        if temp_proxy and os.path.exists(temp_proxy):
            try: os.remove(temp_proxy)
            except Exception: pass


def wait_for_file_active(file_name: str, api_key: str, max_timeout_seconds: int = 180) -> bool:
    url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
    print(f"Waiting for Gemini Files API to process video '{file_name}'...")
    
    start_time = time.time()
    while time.time() - start_time < max_timeout_seconds:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 429:
                from pipeline.gemini import _is_daily_quota_exhausted
                if _is_daily_quota_exhausted(response):
                    print("[JudgeAI] File status call daily quota exhausted. Rotating immediately.")
                    raise requests.exceptions.HTTPError("Daily quota exhausted during file status check", response=response)
                print("[JudgeAI] Polling file status returned 429. Waiting 10 seconds...")
                time.sleep(10)
                continue
            if response.status_code in (500, 502, 503, 504):
                print(f"[JudgeAI] Polling file status returned {response.status_code}. Waiting 5 seconds...")
                time.sleep(5)
                continue
            response.raise_for_status()
            data = response.json()
            state = data.get("state")
            
            if state == "ACTIVE":
                print("Video file is now ACTIVE and ready for query.")
                return True
            elif state == "FAILED":
                raise RuntimeError(f"File processing failed on Gemini Files API: {data}")
            else:
                print(f"Current file state is '{state}'. Retrying in 5 seconds...")
                time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"[JudgeAI] Polling status network/HTTP error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            
    raise TimeoutError("Timeout exceeded waiting for Gemini Files API to activate the file")

def delete_file_from_gemini(file_name: str, api_key: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
    for attempt in range(3):
        try:
            print(f"Cleaning up temporary file {file_name} from Gemini storage (attempt {attempt+1}/3)...")
            response = requests.delete(url, timeout=30)
            if response.status_code == 429:
                time.sleep(5)
                continue
            response.raise_for_status()
            print("File deleted successfully.")
            return
        except Exception as e:
            if attempt == 2:
                print(f"Warning: Failed to delete temporary file {file_name}: {e}")
            time.sleep(3)

class JudgeClient:
    def __init__(self):
        self.base_url = GEMINI_API_BASE
        
    def review_video(self, video_path: str, metadata: dict) -> dict:
        last_error: Exception | None = None
        max_attempts = min(3, len(_shared_pool))
        start_ts = time.time()
        for attempt in range(max_attempts):
            if time.time() - start_ts > 90:
                print("[JudgeAI] Hard timeout (90s) reached. Raising exception to trigger local health fallback.")
                break
            api_key = _get_judge_key(attempt)
            if not api_key:
                break
            slot = _shared_pool._keys.index(api_key) + 1 if api_key in _shared_pool._keys else "DEDICATED"
            try:
                report = self._review_video_with_key(video_path, metadata, api_key)
                if api_key in _shared_pool._keys:
                    _shared_pool.mark_success(api_key)
                return report
            except Exception as exc:
                last_error = exc
                status = _http_status(exc)
                print(f"[JudgeAI] Key slot {slot} failed during review (status {status or 'unknown'}): {exc}")
                if api_key in _shared_pool._keys:
                    _shared_pool.mark_failed(api_key, status or 429, transient=False)
        print(f"[Judge AI] Gemini Files API review skipped or quota exhausted ({last_error}). Running local video health checks...")
        import subprocess
        try:
            dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            dur = float(subprocess.check_output(dur_cmd).decode().strip())
            if dur < 10.0:
                raise RuntimeError(f"Local health check failed: duration {dur:.2f}s is too short (<10s)")
            
            bd_cmd = ["ffmpeg", "-i", video_path, "-vf", "blackdetect=d=0.8:pic_th=0.99:pix_th=0.03", "-f", "null", "-"]
            bd_proc = subprocess.run(bd_cmd, capture_output=True, text=True)
            if "black_start" in bd_proc.stderr:
                print("[Judge AI] Local health check detected black frames!")
                return {"score": 30, "status": "REJECTED", "reason": "Black frames detected by local scanner", "failed_segments": [0, 1]}

            # Deep center-crop luminance check across 4 sample frames to catch dark placeholder/crosshair plates
            import numpy as np
            from PIL import Image
            black_detected = False
            for ts_f in [0.25, 0.50, 0.75]:
                sample_t = max(0.5, dur * ts_f)
                temp_frame = f"output/health_check_frame_{ts_f}.jpg"
                cmd_f = ["ffmpeg", "-y", "-ss", f"{sample_t:.2f}", "-i", video_path, "-vframes", "1", "-q:v", "2", temp_frame]
                subprocess.run(cmd_f, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if os.path.exists(temp_frame):
                    try:
                        with Image.open(temp_frame) as im:
                            gray = np.array(im.convert("L"))
                            ch, cw = gray.shape
                            center_crop = gray[int(ch*0.25):int(ch*0.75), int(cw*0.15):int(cw*0.85)]
                            mean_center = float(np.mean(center_crop))
                            if mean_center < 18.0:
                                black_detected = True
                                print(f"[Judge AI] Frame at t={sample_t:.1f}s is pitch black / dark placeholder (center mean={mean_center:.1f})!")
                    except Exception:
                        pass
                    finally:
                        if os.path.exists(temp_frame):
                            try: os.remove(temp_frame)
                            except Exception: pass
                if black_detected:
                    break

            if black_detected:
                return {
                    "score": 30,
                    "status": "REJECTED",
                    "reason": "Pitch black or blank placeholder screen detected in video.",
                    "failed_segments": [0, 1, 2, 3]
                }
            
            print(f"[Judge AI] Multimodal AI check was unavailable ({last_error}). Format verification OK (duration: {dur:.2f}s), but strictly REJECTING automated publishing to prevent unverified visual slop.")
            return {
                "score": 50,
                "status": "REJECTED",
                "reason": f"Multimodal AI visual check was unavailable ({last_error}). Strictly rejecting auto-publish to prevent video mismatches.",
                "cohesiveness_score": 50,
                "failed_segments": [0, 1, 2, 3, 4]
            }
        except Exception as local_err:
            raise RuntimeError(f"Local video health check failed: {local_err}") from local_err

    def _review_video_with_key(self, video_path: str, metadata: dict, api_key: str) -> dict:
        slot = _shared_pool._keys.index(api_key) + 1 if api_key in _shared_pool._keys else "DEDICATED"
        file_name = None
        try:
            # 1. Upload video
            upload_response = upload_file_to_gemini(video_path, api_key)
            file_info = upload_response.get("file", {})
            file_name = file_info.get("name")
            file_uri = file_info.get("uri")
            mime_type = file_info.get("mimeType")
            
            if not file_name or not file_uri:
                raise RuntimeError(f"Unexpected file upload response: {upload_response}")
                
            # 2. Wait for active status
            wait_for_file_active(file_name, api_key)
            
            # 3. Formulate Prompt
            rubric = f"""You are "Judge AI" (an expert viral media director and quality assurance LLM). Your task is to evaluate the generated educational video and ensure it meets our strict viral criteria.

Video Metadata:
{json.dumps(metadata, indent=2)}

Please watch the video and evaluate it against these rubrics:
1. **Cohesiveness & Alignment (CRITICAL)**: Does the voiceover audio match the visual B-roll clips and the text captions shown on screen?
   - Check for any mismatch (e.g. if the audio discusses "Quantum Computing" but the text caption or B-roll displays terms like "CRISPR" or "Gene Editing").
   - Look out for generic or symbolic placeholders (e.g. a generic man with glasses looking at a screen, generic office workers) that do not directly represent specific scientific/technical/space concepts described in the audio (like 'asteroid wobble', 'planetary defense', 'Bose-Einstein condensate', etc.).
   - STRICT BAN ON IRRELEVANT TERRESTRIAL ANALOGIES: If the video is about Space, Astronomy, Planets, Deep Sea, or Nature, REJECT ANY terrestrial stock footage such as steel mills, factories, foundries, metal smelting, blast furnaces, modern office spaces, traffic, city streets, or beach sunsets. (For example: showing a steel mill foundry when discussing planetary core compression or diamond rain is an UNACCEPTABLE mismatch).
   - STRICT BAN ON ELECTRONICS / WORKBENCH / CAMERA MISMATCHES: If the video is about Nature, Biology, Animals, Extremophiles, or Science, strictly REJECT any footage showing electronics technicians, soldering irons, circuit boards, computer debugging, hardware workshops, camera sensor cleaning, or mechanic tools. (For example: showing a technician soldering or cleaning a camera lens when narration discusses DNA repair or bacterial enzymes is a CRITICAL mismatch).
   - STRICT BAN ON HORROR / MONSTER / DEMON / HALLOWEEN MISMATCHES: Under NO circumstances allow horror-movie monsters, werewolves, alien creatures with claws, Halloween props, or gothic horror CGI when the topic is natural biology, chemistry, warfare tactics, or megaprojects.
2. **Hook Strength (CRITICAL)**: Does the first 2.5 seconds hook the viewer with high visual pacing and immediate high stakes?
3. **No Watermarks or Subtitle Glitches**: Ensure no large watermarks (e.g. iStock, Shutterstock) and no double/colliding subtitles.
4. **No Repeated B-Roll Clips**: Verify that every segment has distinct visual scenes. If any video clip is repeated across multiple segments, fail the repeated segments immediately.
5. **STRICT BAN ON STATIC AI IMAGES / POLLINATIONS SLOP (CRITICAL)**:
   - YouTube Shorts must be REAL, DYNAMIC MOTION VIDEO.
   - REJECT ANY video where segments consist of static 2D AI illustrations, static artwork, fantasy mandala drawings, glowing circular blobs, or still photos with slow Ken Burns pan.
   - If 2 or more segments contain static AI images rather than real dynamic motion footage, you MUST set status="REJECTED", score <= 68, cohesiveness_score <= 50, and flag those segments in failed_segments!
   - Under NO circumstances excuse static AI images as "abstract biological animations" or "creative visuals" — they are static AI slop and MUST BE REJECTED.
6. **STRICT BAN ON BLANK, BLACK, OR RETICLE/CROSSHAIR SCREENS (ZERO TOLERANCE)**:
   - You must verify that EVERY segment displays real, visible subject matter (real animals, machinery, historical scenes, or space).
   - If ANY segment of the video is pitch black, nearly black, or displays only an empty plate or crosshairs with subtitles, you MUST IMMEDIATELY REJECT with status="REJECTED", score <= 30, and list the failed segment IDs in failed_segments!
   - Do NOT assume visual content exists based on what is heard in the audio voiceover. If the visuals are blank/black, FAIL THE VIDEO.

Output strictly valid JSON with this exact schema:
{{
  "score": 91, // 0-100 overall viral score. Videos with ANY irrelevant terrestrial stock analogy, hardware/workbench mismatch, horror monster, repeated clips, blank/black screens, OR STATIC AI SLOP / SLIDESHOWS MUST score <= 70 and fail!
  "status": "PASSED", // "PASSED" if score >= 91 and no critical mismatches/repeated clips/blank screens, otherwise "REJECTED"
  "reason": "Explain the decision in detail",
  "cohesiveness_score": 91, // 0-100 score for audio-visual-caption matching
  "hook_score": 91, // 0-100 score for hook appeal
  "retention_score": 91, // 0-100 score for looping and retention triggers
  "failed_segments": [3, 4], // 0-based indices of segments that had bad B-roll, generic placeholders, mismatches, or static AI slop, or empty [] if none
  "issues": ["List of specific issues found, or empty if none"]
}}
"""
            
            # 4. Generate Review Content (Primary: Gemini 2.5 Flash, Failover: Flash Latest on 503)
            models_to_try = [GEMINI_FLASH, "gemini-flash-latest", "gemini-flash-lite-latest"]
            response = None
            model_success = False
            last_model_err = None

            for model_to_use in models_to_try:
                url = f"{self.base_url}/models/{model_to_use}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"fileData": {"mimeType": mime_type, "fileUri": file_uri}},
                                {"text": rubric}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json"
                    }
                }
                
                print(f"Sending video to model '{model_to_use}' for analysis...")
                for attempt in range(3):
                    try:
                        response = requests.post(url, headers=headers, json=payload, timeout=180)
                        if response.status_code == 429:
                            from pipeline.gemini import _is_daily_quota_exhausted
                            if _is_daily_quota_exhausted(response):
                                print(f"[JudgeAI] Daily quota exhausted on key slot {slot}. Rotating key.")
                                raise requests.exceptions.HTTPError("Daily quota exhausted during review", response=response)
                            wait_s = (attempt + 1) * 10
                            print(f"[JudgeAI] Review call 429 rate limit on '{model_to_use}'. Waiting {wait_s}s...")
                            time.sleep(wait_s)
                            continue
                        if response.status_code in (500, 502, 503, 504):
                            wait_s = (attempt + 1) * 3
                            print(f"[JudgeAI] Review call {response.status_code} server error on '{model_to_use}'. Waiting {wait_s}s...")
                            time.sleep(wait_s)
                            continue
                        response.raise_for_status()
                        model_success = True
                        break
                    except requests.exceptions.HTTPError as he:
                        if "Daily quota exhausted" in str(he):
                            raise
                        last_model_err = he
                    except requests.exceptions.RequestException as e:
                        last_model_err = e
                        wait_s = (attempt + 1) * 3
                        print(f"[JudgeAI] Review call network error on '{model_to_use}': {e}. Waiting {wait_s}s...")
                        time.sleep(wait_s)

                if model_success and response is not None:
                    break
                print(f"[JudgeAI] Model '{model_to_use}' unavailable ({last_model_err}). Failing over to next model...")

            if response is None or not model_success:
                raise RuntimeError(f"Failed to get review response across models: {last_model_err}")
            response_data = response.json()
            
            # Extract and parse response
            try:
                text_response = response_data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as parse_err:
                # If primary failed, we will trigger the fallback check in the except block
                raise RuntimeError(f"Unexpected response format: {response_data}") from parse_err
                
            report = json.loads(_clean_json_output(text_response))
            s = int(report.get("score", 0) or 0)
            c = int(report.get("cohesiveness_score", 100) or 0)
            fs = report.get("failed_segments", [])
            if s < 85 or c < 75 or (isinstance(fs, list) and len(fs) > 0):
                report["status"] = "REJECTED"
            print(f"Judge AI Review complete. Status: {report.get('status')} (Score: {report.get('score')}/100)")
            return report
        finally:
            # Clean up the file in Gemini storage
            if file_name:
                delete_file_from_gemini(file_name, api_key)
