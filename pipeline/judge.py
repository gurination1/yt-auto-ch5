import os
import json
import time
import requests
import mimetypes
import subprocess
import base64
from concurrent.futures import ThreadPoolExecutor
from pipeline.config import GEMINI_FLASH, GEMINI_FLASH_BACKUP, GEMINI_PRO, GEMINI_API_BASE
from pipeline.gemini import _clean_json_output, _shared_pool, _post_with_rotation


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

    # Prioritize keys that are not on active cooldown
    healthy_keys = []
    now = time.time()
    for k in all_keys:
        if hasattr(_shared_pool, "_keys") and k in _shared_pool._keys:
            idx = _shared_pool._keys.index(k)
            if hasattr(_shared_pool, "_cooldowns") and _shared_pool._cooldowns[idx] > now:
                continue
        healthy_keys.append(k)

    pool_to_use = healthy_keys if healthy_keys else all_keys
    chosen_key = pool_to_use[attempt % len(pool_to_use)]
    slot = _shared_pool._keys.index(chosen_key) + 1 if (hasattr(_shared_pool, "_keys") and chosen_key in _shared_pool._keys) else "DEDICATED"
    print(f"[JudgeAI] Selected key slot {slot} for review attempt {attempt + 1}/{len(pool_to_use)}")
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

    def _forensic_review_segments(self, video_path: str, metadata: dict) -> dict | None:
        """
        Forensic Per-Segment Quality Gate:
        1. Checks for visual duplicates across all segments (deterministic pixel diff).
        2. Extracts mid-frame of each segment.
        3. Scrutinizes each segment frame with Gemini Flash Vision against domain rules.
        """
        import numpy as np
        from PIL import Image

        segments = metadata.get("segments", [])
        if not segments:
            return None

        # Determine video duration
        try:
            dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            total_dur = float(subprocess.check_output(dur_cmd).decode().strip())
        except Exception:
            total_dur = 30.0

        num_segs = len(segments)
        seg_dur = total_dur / num_segs
        os.makedirs("output", exist_ok=True)

        frames_data = []
        frame_arrays = []
        failed_segments = []
        issues = []
        seg_scores = [0] * num_segs

        # Step 1: Extract middle frame of each segment
        for idx in range(num_segs):
            broll_file = f"output/broll_{idx}.mp4"
            broll_img = f"output/broll_{idx}.jpg"
            out_frame = f"output/judge_seg_{idx}.jpg"

            extracted = False
            if os.path.exists(broll_file) and os.path.getsize(broll_file) > 10_000:
                try:
                    b_dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", broll_file]
                    b_dur = float(subprocess.check_output(b_dur_cmd, timeout=5).decode().strip())
                    ss = max(0.5, min(b_dur - 0.5, b_dur * 0.5))
                except Exception:
                    ss = 1.0
                cmd = ["ffmpeg", "-y", "-ss", f"{ss:.2f}", "-i", broll_file, "-vf", "scale=-2:720", "-vframes", "1", "-q:v", "2", out_frame]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                if os.path.exists(out_frame) and os.path.getsize(out_frame) > 1000:
                    extracted = True

            if not extracted and os.path.exists(broll_img) and os.path.getsize(broll_img) > 1000:
                import shutil
                shutil.copy(broll_img, out_frame)
                extracted = True

            if not extracted:
                ss = idx * seg_dur + seg_dur * 0.5
                cmd = ["ffmpeg", "-y", "-ss", f"{ss:.2f}", "-i", video_path, "-vf", "scale=-2:720", "-vframes", "1", "-q:v", "2", out_frame]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                if os.path.exists(out_frame) and os.path.getsize(out_frame) > 1000:
                    extracted = True

            if not extracted:
                failed_segments.append(idx)
                issues.append(f"Segment {idx+1}: Missing or unextractable video frame")
                frames_data.append(None)
                frame_arrays.append(None)
                continue

            # Check black/blank screen locally
            try:
                with Image.open(out_frame) as im:
                    gray = np.array(im.convert("L"))
                    mean_lum = float(np.mean(gray))
                    std_lum = float(np.std(gray))
                    if mean_lum < 8.0 and std_lum < 8.0:
                        failed_segments.append(idx)
                        issues.append(f"Segment {idx+1}: Pitch black screen (mean={mean_lum:.1f})")
                    elif mean_lum > 225.0 and std_lum < 20.0:
                        failed_segments.append(idx)
                        issues.append(f"Segment {idx+1}: Blank white screen (mean={mean_lum:.1f})")

                    thumb = np.array(im.convert("L").resize((64, 64)), dtype=float)[12:52, :]
                    frame_arrays.append(thumb)
            except Exception:
                frame_arrays.append(None)

            frames_data.append(out_frame)

        # Step 2: Deterministic Duplicate Detection across all segment pairs
        for i in range(num_segs):
            if frame_arrays[i] is None:
                continue
            for j in range(i + 1, num_segs):
                if frame_arrays[j] is None:
                    continue
                diff = float(np.mean(np.abs(frame_arrays[i] - frame_arrays[j])))
                if diff < 22.0:
                    print(f"[Judge AI] DUPLICATE DETECTED between Segment {i+1} and Segment {j+1} (pixel diff: {diff:.2f})!")
                    if j not in failed_segments:
                        failed_segments.append(j)
                        issues.append(f"Segment {j+1}: Visual duplicate of Segment {i+1} (pixel diff {diff:.1f})")

        # Step 2b: Forensic Script Narration Audit (Detect Inter-Segment Repetition & Qualifying Rut Loops)
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "into", "they", "them", "their",
            "have", "been", "were", "will", "would", "could", "should", "about", "more", "most",
            "some", "what", "when", "where", "which", "while", "because", "also", "just", "only",
            "very", "even", "then", "than", "over", "each", "every", "these", "those", "such"
        }
        for i in range(num_segs):
            narr_i = segments[i].get("narration", "").strip()
            words_i = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', narr_i.lower()) if w not in stop_words]
            tokens_i = narr_i.lower().split()
            clause_i = " ".join(tokens_i[:4]) if len(tokens_i) >= 4 else ""

            for j in range(i + 1, num_segs):
                narr_j = segments[j].get("narration", "").strip()
                words_j = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', narr_j.lower()) if w not in stop_words]
                tokens_j = narr_j.lower().split()
                clause_j = " ".join(tokens_j[:4]) if len(tokens_j) >= 4 else ""

                common_prefix = (clause_i == clause_j) and len(clause_i) > 8

                has_4gram = False
                for k in range(len(tokens_i) - 3):
                    ngram = " ".join(tokens_i[k:k+4])
                    if ngram in narr_j.lower():
                        has_4gram = True
                        break

                overlap = set(words_i) & set(words_j)
                min_w = min(len(set(words_i)), len(set(words_j))) if (words_i and words_j) else 0
                overlap_ratio = len(overlap) / min_w if min_w > 0 else 0.0

                if common_prefix or has_4gram or (len(overlap) >= 3 and overlap_ratio >= 0.35):
                    print(f"[Judge AI] SCRIPT REPETITION DETECTED between Seg {i+1} and Seg {j+1}! Overlap: {overlap}, 4-gram: {has_4gram}, prefix: {common_prefix}")
                    if j not in failed_segments:
                        failed_segments.append(j)
                    issues.append(f"Segment {j+1}: Script narration repeats phrasing/claims from Segment {i+1} ('{narr_j[:40]}...')")

        # Step 2c: Dopamine Loop & Narrative Tension Scrutiny
        if num_segs >= 3:
            first_narr = segments[0].get("narration", "").strip().lower()
            forbidden_starts = ("did you know", "have you ever", "what if", "could it be", "imagine if", "can you believe")
            if any(first_narr.startswith(fs) for fs in forbidden_starts):
                print(f"[Judge AI] NARRATIVE VIOLATION: Segment 1 starts with forbidden rhetorical question ('{first_narr[:30]}...')!")
                if 0 not in failed_segments:
                    failed_segments.append(0)
                issues.append("Segment 1: Starts with passive rhetorical question instead of immediate high-stakes physical fact.")

            last_narr = segments[-1].get("narration", "").lower()
            spam_triggers = ("link in bio", "subscribe", "follow for more", "check bio", "link in description")
            if any(st in last_narr for st in spam_triggers):
                print(f"[Judge AI] NARRATIVE VIOLATION: Final segment contains spoken social spam ('{last_narr[:40]}...')!")
                last_idx = num_segs - 1
                if last_idx not in failed_segments:
                    failed_segments.append(last_idx)
                issues.append("Final Segment: Contains forbidden spoken social spam ('link in bio' / 'subscribe').")

        # Step 3: Per-segment forensic audit with Gemini Vision
        title = metadata.get("title", "")

        def audit_single_segment(seg_tuple):
            idx, seg = seg_tuple
            out_frame = frames_data[idx]
            if not out_frame or not os.path.exists(out_frame) or idx in failed_segments:
                return idx, 20, False, False, "Duplicate, repetitive, or unextractable frame", ""

            narration = seg.get("narration", "")
            broll_q = seg.get("broll_query") or seg.get("query") or seg.get("narration", "")

            try:
                with open(out_frame, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()

                prompt = f"""You are a ruthless forensic media director and quality assurance judge inspecting a video segment.
Video Title: "{title}"
Segment {idx+1} Narration: "{narration}"
Target B-roll Entity: "{broll_q}"

Scrutinize this actual frame extracted from the video segment with brutal honesty.
CRITICAL REJECTION RULES (Mark mismatch_detected=true or slop_detected=true if violated):
1. WRONG BRAND / STOREFRONT: If topic is a specific company/brand (e.g. Hermès, Ferrari, Apple), B-roll MUST NOT show unrelated retail storefronts (e.g. Scully & Scully), wrong logos, or domestic shops.
2. DOMESTIC / NOVELTY SLOP: If narration describes six-figure luxury, industrial engineering, or high finance, strictly REJECT ordinary kitchen cupboards, novelty coffee mugs with cartoon prints, or everyday home dishware.
3. CHEAP PROPS & TOYS: Strictly reject miniature toy purses, faux leather 4-inch props held in hands, plastic desk toys, or amateur mockups.
4. ANACHRONISMS IN HISTORY: Strictly reject modern civilian clothing (t-shirts, jeans, hoodies), modern living rooms, or DIY craft tables in ancient/medieval history.
5. METALLURGY / RUBBLE: Strictly reject blurry piles of gravel or dirt clods when narration describes weapons, metallurgy, or engineering.
6. FANTASY / AI SLOP / CGI: Strictly reject fantasy art, anime, CGI wizards/monsters, or static illustrations with watermarks.
7. SLIDES & TEXT: Strictly reject PowerPoint slides, text documents, or software tutorials.
8. TALKING HEADS: Strictly reject vloggers, facecams, or podcast hosts.
9. BAKED-IN SUBTITLES & WATERMARKS: Strictly reject any source footage that has pre-existing English subtitles, hardcoded caption banners, news channel ticker bars, or creator watermark text burned into the video frame.
10. SCREENSHOTS & SOFTWARE UI: Strictly reject web browser screenshots, cookie consent popups, website dialog banners, computer desktop windows, Google Maps screengrabs, phone UI screenshots, or software code windows. Visuals must be real, physical, cinematic footage or authentic physical photographs of real-world objects, places, or machinery!

Return JSON ONLY:
{{
  "visible_subject": "1 concise sentence describing what is physically visible",
  "relevance_score": 1-100,
  "mismatch_detected": false,
  "slop_detected": false,
  "critique": "Brutally honest critique"
}}"""

                payload = {
                    "contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": b64}}]}],
                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
                }
                url = f"{self.base_url}/models/{GEMINI_FLASH}:generateContent?key={{key}}"
                resp = _post_with_rotation(url, payload, timeout=25)

                if resp and resp.status_code == 200:
                    cand = resp.json().get("candidates", [{}])[0]
                    raw = cand.get("content", {}).get("parts", [{}])[0].get("text", "")
                    data = json.loads(_clean_json_output(raw))
                    rel_score = int(data.get("relevance_score", 50))
                    mismatch = bool(data.get("mismatch_detected", False))
                    slop = bool(data.get("slop_detected", False))
                    critique = str(data.get("critique", ""))
                    subj = str(data.get("visible_subject", ""))
                    return idx, rel_score, mismatch, slop, critique, subj
                else:
                    return idx, 70, False, False, "Vision API unavailable", ""
            except Exception as e_seg:
                return idx, 70, False, False, f"Audit error: {e_seg}", ""

        with ThreadPoolExecutor(max_workers=min(4, num_segs)) as executor:
            futures = [executor.submit(audit_single_segment, (i, seg)) for i, seg in enumerate(segments)]
            for fut in futures:
                s_idx, s_rel, s_mis, s_slop, s_crit, s_subj = fut.result()
                seg_scores[s_idx] = s_rel
                print(f"[Judge AI | Seg {s_idx+1}] Subj: {s_subj[:40]}... | Score: {s_rel}/100 | Mismatch: {s_mis} | Slop: {s_slop}")
                if s_rel < 80 or s_mis or s_slop:
                    if s_idx not in failed_segments:
                        failed_segments.append(s_idx)
                    issues.append(f"Segment {s_idx+1} ('{segments[s_idx].get('broll_query', '')}'): {s_crit} (Score: {s_rel}/100)")

        # Step 4: Final Score Compilation
        failed_segments = sorted(list(set(failed_segments)))
        avg_score = int(sum(seg_scores) / len(seg_scores)) if seg_scores else 50

        if failed_segments or avg_score < 85:
            final_status = "REJECTED"
            final_score = max(20, min(80, avg_score))
            if not failed_segments and avg_score < 85:
                lowest_idx = int(np.argmin(seg_scores)) if len(seg_scores) > 0 else 0
                failed_segments = [lowest_idx]
                issues.append(f"Average score {avg_score}/100 below 85 pass threshold. Segment {lowest_idx+1} lowest score ({seg_scores[lowest_idx]}/100).")
            reason = f"Forensic Review FAILED: {len(failed_segments)} segment(s) rejected: {failed_segments}. Issues: " + "; ".join(issues[:3])
        else:
            final_status = "PASSED"
            final_score = avg_score
            reason = f"Forensic Review PASSED: All {num_segs} segments verified authentic (Average Score: {final_score}/100)."

        print(f"[Judge AI] Forensic Audit Result: Status={final_status}, Score={final_score}/100, Failed Segments={failed_segments}")
        return {
            "score": final_score,
            "status": final_status,
            "reason": reason,
            "cohesiveness_score": final_score,
            "hook_score": seg_scores[0] if seg_scores else final_score,
            "retention_score": final_score,
            "failed_segments": failed_segments,
            "issues": issues,
            "forensic_audit": True
        }

    def review_video(self, video_path: str, metadata: dict) -> dict:
        # Priority 1: Rigorous forensic per-segment visual audit & deterministic duplicate detection
        try:
            print("[Judge AI] Initiating Forensic Per-Segment Visual & Alignment Audit...")
            forensic_report = self._forensic_review_segments(video_path, metadata)
            if forensic_report is not None:
                return forensic_report
        except Exception as e_forensic:
            print(f"[Judge AI] Forensic per-segment audit exception: {e_forensic}. Falling back to holistic video review...")

        last_error: Exception | None = None
        pool_len = len(_shared_pool) if hasattr(_shared_pool, "_keys") else 5
        max_attempts = min(10, pool_len)
        start_ts = time.time()
        for attempt in range(max_attempts):
            if time.time() - start_ts > 150:
                print("[JudgeAI] Hard timeout (150s) reached. Raising exception to trigger local health fallback.")
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
                _FAILED_JUDGE_KEYS.add(api_key)
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
7. **STRICT FOCAL SUBJECT VISIBILITY & ANTI-HALLUCINATION (ZERO TOLERANCE)**:
   - DO NOT assume visual content exists based on what is heard in the audio voiceover! Inspect the ACTUAL video frames:
   - If a segment describes a specific focal animal, creature, organism, or machine (e.g. rat, rodent, beetle, squid, worm, ant, snake, elephant, predator, tunnel boring machine), THE ACTUAL CREATURE OR MACHINE MUST BE CLEARLY VISIBLE in the video pixels!
   - Reject immediately (status="REJECTED", score <= 60, and flag segment index in failed_segments) if the segment only shows empty bushes, dark night-vision background without the animal, a vehicle/jeep without the animal, an empty cage, or distant blurred scenery.
   - For ancient/medieval history topics, reject modern concrete dams/bridges, electric streetlights, power lines, and modern clothing.
   - For industrial, engineering, or commodity topics, reject domestic kitchen baking, cake batter, and whisks.
   - Reject any segment with >60% blank/solid white canvas.
8. **STRICT DOMAIN PURITY & ZERO METAPHOR LEAKS (ZERO TOLERANCE)**:
   - Nature / Wildlife: STRICTLY ZERO modern cars, vintage 1950s automobiles, asphalt streets, rain puddles, or urban weather storms when narration uses metaphorical phrases like "chemical flood", "nerve storm", or "fluid rush".
   - Ancient History: STRICTLY ZERO modern 20th-century concrete gravity dams, electric streetlights, or power transmission lines.
   - Science / Business: STRICTLY ZERO Windows desktop screencasts, WinRAR/software windows, or domestic kitchen bread baking.
9. **STRICT PER-SEGMENT CONTEXT & ZERO IRRELEVANT STOCK (CRITICAL)**:
   - For ancient engineering/history (e.g. Roman concrete, aqueducts, ancient structures): STRICTLY REJECT Christian monks, saints, religious fresco icons, clerics, or cathedral altars unless narration explicitly discusses religion.
   - For architecture/engineering/luxury: STRICTLY REJECT generic corporate office elevator lobbies, hallways, exit corridors, or building evacuation plans.
   - For materials science/construction/geology: STRICTLY REJECT blurry rubber or latex medical gloves, dishwashing gloves, or sterile exam rooms when discussing concrete, stone, or minerals.
   - If ANY segment exhibits these irrelevant visual substitutions, score MUST be <= 65 and status="REJECTED".
10. **STRICT BAN ON SCREENSHOTS & SOFTWARE UI (CRITICAL)**:
    - YouTube Shorts must display cinematic real-world footage or physical objects.
    - STRICTLY REJECT ANY video containing computer desktop screencasts, web browser tabs, cookie consent dialog banners, Google Maps routes, or phone UI screenshots.
    - If ANY segment displays a software window, browser dialog, or UI screenshot, score MUST be <= 65 and status="REJECTED".
11. **DOPAMINE ADDICTION LOOP & NARRATIVE TENSION (CRITICAL)**:
    - **High Stakes (Segment 1)**: Must establish immediate consequence, peril, or active physical fact (NO passive lecturing, NO "Did you know?", NO rhetorical questions).
    - **The Headfake / Prediction Error (Middle Segments)**: Must contain an active expectation subversion ("You'd think X, but the reality is Y", or showing where obvious theories failed) to prevent mid-video drop-off.
    - **Core Breakthrough Payoff**: Must deliver the verified real answer before the ending (no cliffhanger cop-outs).
    - **Seamless Infinite Loop**: Final segment must redeal tension and bridge back to the opening hook without spoken social media spam ("subscribe", "link in bio").
    - Scripts that read like flat textbook lectures lacking storytelling tension or prediction errors MUST score <= 70 and fail!

Output strictly valid JSON with this exact schema:
{{
  "score": 90, // 0-100 overall viral score. Videos with strong audio-visual alignment, real dynamic footage, and NO mismatches/blank screens score in the 88-96 range! Videos with ANY irrelevant terrestrial stock analogy, hardware/workbench mismatch, horror monster, repeated clips, blank/black screens, monk/elevator/glove mismatch, OR STATIC AI SLOP / SLIDESHOWS MUST score <= 70 and fail!
  "status": "PASSED", // "PASSED" if score >= 85 and no critical mismatches/repeated clips/blank screens, otherwise "REJECTED"
  "reason": "Explain the decision in detail",
  "cohesiveness_score": 90, // 0-100 score for audio-visual-caption matching
  "hook_score": 90, // 0-100 score for hook appeal
  "retention_score": 90, // 0-100 score for looping and retention triggers
  "failed_segments": [3, 4], // 0-based indices of segments that had bad B-roll, generic placeholders, mismatches, or static AI slop, or empty [] if none
  "issues": ["List of specific issues found, or empty if none"]
}}
"""
            
            # 4. Generate Review Content (Production Flash models only)
            models_to_try = [
                GEMINI_FLASH,
                GEMINI_FLASH_BACKUP,
                GEMINI_PRO,
            ]
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
                                print(f"[JudgeAI] Daily quota for '{model_to_use}' exhausted on key slot {slot}. Trying fallback model...")
                                last_model_err = f"Daily quota exhausted on {model_to_use}"
                                break
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
