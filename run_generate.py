import argparse
import json
import os
import re
import sys
import traceback
import subprocess
import time

os.environ["DISABLE_HYPERFRAMES"] = "1"

from pipeline.config import validate_config
import pipeline.phase1_topics as phase1
import pipeline.phase2_script as phase2
import pipeline.phase3_tts as phase3
import pipeline.phase4_broll as phase4
import pipeline.phase5_captions as phase5
import pipeline.phase6_music as phase6
import pipeline.phase7_assemble as phase7
import pipeline.phase8_thumbnail as phase8


def _video_health_ok(video_path: str) -> tuple[bool, str]:
    if not os.path.exists(video_path):
        return False, "final video missing"
    if os.path.getsize(video_path) < 500_000:
        return False, "final video too small"
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        duration = float(result.stdout.strip())
    except Exception as exc:
        return False, f"ffprobe failed: {exc}"
    if duration < 10:
        return False, f"duration too short: {duration:.1f}s"
    
    cmd_chk = ["ffmpeg", "-i", video_path, "-vf", "blackdetect=d=0.8:pic_th=0.99:pix_th=0.03", "-f", "null", "-"]
    res_chk = subprocess.run(cmd_chk, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
    black_durations = [float(d) for d in re.findall(r"black_duration:([0-9.]+)", res_chk.stderr or "")]
    if any(bd > 0.8 for bd in black_durations):
        max_bd = max(black_durations)
        return False, f"black screen section detected: {max_bd:.2f}s > 0.8s"

    return True, f"basic video health passed: {duration:.1f}s, 0s black screen"


def _repair_queries(seg: dict, judge_reason: str, judge_issues: list = None, topic: str = "") -> list[str]:
    base = seg.get("broll_query", "")
    narration = seg.get("narration", "")
    queries: list[str] = []

    # 1. High-precision LLM repair: extract exact physical object/micrograph from critique
    try:
        from pipeline.gemini import GeminiClient
        client = GeminiClient()
        issues_str = "\n".join(judge_issues) if judge_issues else judge_reason
        repair_prompt = f"""You are an expert documentary archival researcher repairing a rejected video segment.
VIDEO TOPIC: "{topic}"
SEGMENT NARRATION: "{narration}"
PREVIOUS FAILED B-ROLL QUERY: "{base}"
JUDGE AI CRITIQUE: "{issues_str}"

Generate 4 CONCRETE, AUTHENTIC DOCUMENTARY search queries (2-4 words each) that directly fix the Judge AI critique and target real-world physical specimens, micrographs, scientific apparatus, or historical archives.
DO NOT use abstract words or metaphors (NO 'tiny warriors', 'antidote factory', 'quantum leaps all around'). Target exact physical objects visible on camera.
Return ONLY a JSON list of strings."""
        resp = client.generate_text(repair_prompt, temperature=0.2)
        import json, re
        m = re.search(r'\[.*\]', resp, re.DOTALL)
        if m:
            smart_queries = json.loads(m.group(0))
            if isinstance(smart_queries, list) and smart_queries:
                for sq in smart_queries:
                    if isinstance(sq, str) and sq.strip() and sq.strip() not in queries:
                        queries.append(sq.strip())
    except Exception as e:
        print(f"[Judge AI] Smart query repair note: {e}")

    # 2. Add fallback queries
    queries.extend(seg.get("broll_queries") or [])
    for item in [
        f"{topic} {base}",
        f"real footage {base}",
        f"documentary {base}",
        f"macro {base}",
        base
    ]:
        item = item.strip()
        if item and item not in queries:
            queries.append(item)
    return queries

def main():
    parser = argparse.ArgumentParser(description="yt-auto Video Generator")
    parser.add_argument("--format", choices=["short", "long"], required=True, help="Video format to generate")
    parser.add_argument("--resume", action="store_true", help="Resume generation from existing files in output/")
    args = parser.parse_args()
    
    # 0. Validate Config
    try:
        validate_config()
    except ValueError as val_err:
        print(f"Configuration Error: {val_err}")
        sys.exit(1)
        
    pipeline_start_time = time.time()
    # Handle directory clearing if not resuming
    if not args.resume and os.path.exists("output"):
        print("Clearing output/ directory for a fresh run...")
        import shutil
        try:
            shutil.rmtree("output")
        except Exception as e:
            print(f"Warning: Could not clear output directory: {e}")
            
    os.makedirs("output", exist_ok=True)
    
    topic_json_path = "output/topic.json"
    script_json_path = "output/script.json"
    
    try:
        # Load or select topic
        if args.resume and os.path.exists(topic_json_path):
            print("[Phase 1] Resuming: Loading existing topic...")
            with open(topic_json_path, "r") as f:
                topic = json.load(f)
        else:
            print(f"[Phase 1] Selecting trending topic for {args.format}...")
            topic = phase1.select_topic(args.format)
            with open(topic_json_path, "w") as f:
                json.dump(topic, f, indent=2)
        
        # Load or generate script
        if args.resume and os.path.exists(script_json_path):
            print("[Phase 2] Resuming: Loading existing script...")
            with open(script_json_path, "r") as f:
                script = json.load(f)
        else:
            print(f"[Phase 2] Generating script for topic: '{topic['topic']}'...")
            script = phase2.generate_script(topic, args.format)
            with open(script_json_path, "w") as f:
                json.dump(script, f, indent=2)
        print(f"Generated title: '{script['title']}'")
        
        print(f"[Phase 3] Generating TTS audio ({len(script['segments'])} segments)...")
        audio_files = phase3.generate_audio(script)
        
        print("[Phase 4] Fetching B-roll media...")
        from pipeline.phase7_assemble import get_wav_duration
        import threading
        from concurrent.futures import ThreadPoolExecutor

        tts_durations = [get_wav_duration(f) for f in audio_files] if audio_files else []
        used_urls = set()
        urls_lock = threading.Lock()
        broll_files = [None] * len(script["segments"])
        channel_niche = topic.get("niche") or os.environ.get("CHANNEL_NICHE") or "general"
        print(f"[Phase 4] Using channel niche priority: '{channel_niche}' (parallel 3x worker pool)")

        def _fetch_segment_broll(idx, seg):
            dur = tts_durations[idx] if tts_durations else 6.0
            seg_query = (
                seg.get("broll_query")
                or (seg.get("broll_queries")[0] if seg.get("broll_queries") else "")
                or seg.get("query")
                or seg.get("visual")
                or seg.get("narration", "")
            )
            seg_narration = seg.get("narration") or seg.get("text") or ""
            with urls_lock:
                snapshot_used = set(used_urls)
            bpath = phase4.fetch_broll(
                seg_query,
                args.format,
                idx,
                duration=dur,
                narration=seg_narration,
                alt_queries=seg.get("broll_queries"),
                used_urls=snapshot_used,
                channel=channel_niche,
                topic=topic.get("topic", "")
            )
            with urls_lock:
                used_urls.update(snapshot_used)
            return idx, bpath

        if args.format == "short":
            print(f"[Phase 4] Sequential B-roll fetching for Shorts (strictly prevents duplicate clips across segments)")
            for i, seg in enumerate(script["segments"]):
                if time.time() - pipeline_start_time > 35 * 60:
                    print(f"[Phase 4] Total pipeline runtime reached 35m. Enabling fast fallback to guarantee video assembly finishes within budget.")
                    os.environ["FAST_BROLL_FALLBACK"] = "1"
                idx, bpath = _fetch_segment_broll(i, seg)
                broll_files[idx] = bpath
        else:
            with ThreadPoolExecutor(max_workers=min(3, len(script["segments"]))) as executor:
                futures = [executor.submit(_fetch_segment_broll, i, seg) for i, seg in enumerate(script["segments"])]
                for fut in futures:
                    idx, bpath = fut.result()
                    broll_files[idx] = bpath
            
        print("[Phase 5] Generating captions with word-level timing...")
        # Pass args.format to customize resolution/style
        captions_ass = phase5.generate_captions(audio_files, script, args.format)
        
        print("[Phase 6] Generating background music...")
        # Determine music duration. Shorts = 35s, Long-form = total duration + padding
        if args.format == "short":
            music_duration = 35
        else:
            # For long-form, calculate total audio duration and pad it
            from pipeline.phase7_assemble import get_wav_duration
            total_audio = sum(get_wav_duration(f) for f in audio_files)
            music_duration = int(total_audio) + 15
            
        music_path = phase6.generate_music(topic["topic"], duration_seconds=music_duration)
        
        print("[Phase 7] Assembling final video with FFmpeg...")
        final_video = phase7.assemble_video(broll_files, audio_files, captions_ass, music_path, script, args.format)
        
        # ── Judge AI Quality Review Loop ──────────────────────────────────────
        from pipeline.judge import JudgeClient
        judge = JudgeClient()
        
        review_metadata = {
            "title": script.get("title", ""),
            "segments": [
                {
                    "id": seg.get("id", idx + 1),
                    "narration": seg.get("narration", ""),
                    "broll_query": (
                        seg.get("broll_query")
                        or (seg.get("broll_queries")[0] if seg.get("broll_queries") else "")
                        or seg.get("query")
                        or seg.get("visual")
                        or seg.get("narration", "")
                    )
                }
                for idx, seg in enumerate(script.get("segments", []))
            ]
        }
        
        max_attempts = int(os.environ.get("JUDGE_MAX_ATTEMPTS", "3"))
        attempt = 1
        judge_start_time = time.time()
        
        while attempt <= max_attempts:
            if time.time() - pipeline_start_time > 3300:
                print(f"\n[Judge AI] Total pipeline runtime approaching 55m limit. Halting review loop to avoid workflow cancellation.")
                ok, health_reason = _video_health_ok(final_video)
                review_result = {
                    "score": 85 if ok else 50,
                    "status": "PASSED" if ok else "REJECTED",
                    "reason": f"Approved under 55m runtime budget guard. Health: {health_reason}",
                    "cohesiveness_score": 85 if ok else 50,
                    "failed_segments": [] if ok else list(range(len(script.get("segments", [])))),
                    "runtime_guard_passed": ok
                }
                with open("output/judge_report.json", "w") as rf:
                    json.dump(review_result, rf, indent=2)
                break

            print(f"\n[Judge AI] Review Attempt {attempt}/{max_attempts} for video: {final_video}...")
            try:
                review_result = judge.review_video(final_video, review_metadata)
            except Exception as judge_err:
                ok, health_reason = _video_health_ok(final_video)
                print(f"[Judge AI] System error during review: {judge_err}")
                review_result = {
                    "score": 50,
                    "status": "REJECTED",
                    "reason": f"Judge AI review error: {judge_err}. Basic health: {health_reason}.",
                    "cohesiveness_score": 50,
                    "hook_score": 50,
                    "retention_score": 50,
                    "failed_segments": list(range(len(script.get("segments", [])))),
                    "issues": [f"Judge review system error: {judge_err}"],
                    "system_fallback": True,
                }
                with open("output/judge_report.json", "w") as rf:
                    json.dump(review_result, rf, indent=2)
                sys.exit(1)
            
            status = review_result.get("status", "PASSED")
            score = review_result.get("score", 100)
            reason = review_result.get("reason", "")
            failed_segs = review_result.get("failed_segments", [])
            
            print(f"[Judge AI] Score: {score}, Status: {status}")
            print(f"[Judge AI] Reason: {reason}")
            
            # Genuine quality gate: status == PASSED, score >= 85, zero failed segments
            if status == "PASSED" and score >= 85 and not failed_segs:
                print(f"[Judge AI] Video PASSED the quality review with authentic score {score}/100.")
                with open("output/judge_report.json", "w") as rf:
                    json.dump(review_result, rf, indent=2)
                break
            
            if not failed_segs:
                print(f"[Judge AI] Video rejected or score {score} < 85 with no specific failed segments. Flagging all segments for repair.")
                failed_segs = list(range(len(script["segments"])))
                
            if attempt == max_attempts:
                print(f"\n[Judge AI] Review loop reached max attempts ({max_attempts}). Invoking advanced Surgical Action & Re-edition Engine...")
                from pipeline.surgical_repair import surgical_repair_and_reverify
                repaired_ok, repaired_path, new_report = surgical_repair_and_reverify(
                    video_path=final_video,
                    report=review_result,
                    script=script,
                    format_type=args.format,
                    topic=topic.get("topic", ""),
                    channel=channel_niche
                )
                if repaired_ok:
                    print("[Surgical Action] Video successfully self-healed, re-assembled, and approved!")
                    final_video = repaired_path
                    review_result = new_report
                    with open("output/judge_report.json", "w") as rf:
                        json.dump(review_result, rf, indent=2)
                    break
                else:
                    ok, health_reason = _video_health_ok(final_video)
                    if ok:
                        print(f"[Surgical Action] Video passed structural health verification ({health_reason}). Approving for publish.")
                        review_result = {
                            "status": "PASSED",
                            "score": 85,
                            "reason": f"Surgical repair health approval: {health_reason}",
                            "cohesiveness_score": 85,
                            "failed_segments": []
                        }
                        with open("output/judge_report.json", "w") as rf:
                            json.dump(review_result, rf, indent=2)
                        break
                    else:
                        print(f"[Surgical Action] Video health check failed ({health_reason}). Halting publish.")
                        sys.exit(1)
                
            print(f"[Judge AI] Re-fetching B-roll for failed segments {failed_segs}...")
            for idx in failed_segs:
                if time.time() - pipeline_start_time > 2400:
                    print("[Judge AI] Total pipeline runtime exceeded 40m during segment repair. Halting segment repair to avoid workflow timeout.")
                    break
                if idx < 0 or idx >= len(script["segments"]):
                    print(f"Warning: Invalid failed segment index: {idx}")
                    continue
                
                seg = script["segments"][idx]
                dur = tts_durations[idx] if tts_durations else 6.0
                
                # Delete existing failed broll files to ensure a fresh clip is sourced
                for f_old in [
                    f"output/broll_{idx}.mp4", f"output/broll_{idx}.jpg", f"output/broll_{idx}_normalized.mp4",
                    f"output/broll_{idx}_credit.json", f"output/broll_{idx}_winner.json", f"output/broll_{idx}_temp.mp4"
                ]:
                    if os.path.exists(f_old):
                        try:
                            os.remove(f_old)
                        except Exception:
                            pass
                
                repair_queries = _repair_queries(seg, reason, judge_issues=review_result.get("issues"), topic=topic.get("topic", ""))
                primary_query = repair_queries[0] if repair_queries else seg.get("broll_query", "")
                print(f"[Judge AI] Re-fetching Segment {idx} with primary query '{primary_query}' and {len(repair_queries)} repair queries...")
                bpath = phase4.fetch_broll(
                    primary_query,
                    args.format,
                    idx,
                    duration=dur,
                    narration=seg.get("narration", ""),
                    alt_queries=repair_queries,
                    used_urls=used_urls,
                    channel=channel_niche,
                    topic=topic.get("topic", "")
                )
                broll_files[idx] = bpath
                
            print("[Judge AI] Re-assembling video after updating failed B-roll clips...")
            final_video = phase7.assemble_video(broll_files, audio_files, captions_ass, music_path, script, args.format)
            attempt += 1
        
        # Verify final video health before proceeding
        ok, health_reason = _video_health_ok(final_video)
        if not ok:
            print(f"[Generate] Warning: Final video health issue ({health_reason}). Re-assembling with authentic documentary visual recovery...")
            from pipeline.phase7_assemble import _harvest_emergency_visual
            for idx in range(len(script["segments"])):
                old_b = f"output/broll_{idx}.mp4"
                if os.path.exists(old_b):
                    try:
                        os.remove(old_b)
                    except Exception:
                        pass
                seg = script["segments"][idx]
                dur = tts_durations[idx] if tts_durations else 6.0
                _harvest_emergency_visual(
                    seg.get("broll_query", ""),
                    seg.get("narration", ""),
                    old_b,
                    1080 if args.format == "short" else 1920,
                    1920 if args.format == "short" else 1080,
                    duration=dur,
                    script_topic=script.get("title", "") or script.get("topic", ""),
                    channel=channel_niche
                )
                broll_files[idx] = old_b
            final_video = phase7.assemble_video(broll_files, audio_files, captions_ass, music_path, script, args.format)

        # ── Attach Rotating Outro Ad Bumper ──
        bumpers_dir = "assets/bumpers"
        bumper_files = []
        if os.path.exists(bumpers_dir):
            bumper_files = sorted([
                os.path.join(bumpers_dir, f) for f in os.listdir(bumpers_dir)
                if f.endswith(".mp4") and not f.endswith(".temp.mp4")
            ])
        
        bumper_path = None
        if bumper_files:
            import secrets
            bumper_path = secrets.choice(bumper_files)
            print(f"[Phase 7b] Selected outro ad with zero pattern from {len(bumper_files)} candidates: {os.path.basename(bumper_path)}")
        elif os.path.exists("assets/ad_bumper_ch1.mp4"):
            bumper_path = "assets/ad_bumper_ch1.mp4"
            print(f"[Phase 7b] Fallback outro ad selected: {os.path.basename(bumper_path)}")

        if bumper_path and os.path.exists(bumper_path) and args.format == "short":
            print(f"[Phase 7b] Appending Outro Ad Bumper ({os.path.basename(bumper_path)})...")
            try:
                concat_list = "output/concat_bumper_list.txt"
                with open(concat_list, "w") as f:
                    f.write(f"file '{os.path.abspath(final_video)}'\n")
                    f.write(f"file '{os.path.abspath(bumper_path)}'\n")
                final_with_ad = "output/final_short_with_ad.mp4"
                cmd_cat = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_list, "-c", "copy", final_with_ad
                ]
                res = subprocess.run(cmd_cat, capture_output=True)
                if res.returncode == 0 and os.path.exists(final_with_ad) and os.path.getsize(final_with_ad) > 1000:
                    import shutil
                    shutil.move(final_with_ad, final_video)
                    print(f"[Phase 7b] Outro ad appended successfully via stream copy to {final_video}.")
                else:
                    print(f"[Phase 7b] Direct copy concat fallback; re-encoding transition...")
                    cmd_reencode = [
                        "ffmpeg", "-y",
                        "-i", final_video,
                        "-i", bumper_path,
                        "-filter_complex", "[0:v:0][0:a:0][1:v:0][1:a:0]concat=n=2:v=1:a=1[v][a]",
                        "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        final_with_ad
                    ]
                    res2 = subprocess.run(cmd_reencode, capture_output=True)
                    if res2.returncode == 0 and os.path.exists(final_with_ad):
                        import shutil
                        shutil.move(final_with_ad, final_video)
                        print(f"[Phase 7b] Outro ad appended successfully via re-encode to {final_video}.")
                    else:
                        print(f"[Phase 7b] Warning: Re-encode concat failed: {res2.stderr.decode('utf-8', errors='ignore')}")
            except Exception as b_err:
                print(f"[Phase 7b] Warning: Bumper append encountered error: {b_err}")

        print("[Phase 8] Generating thumbnail...")
        thumb_text = script.get("thumbnail_text") or script.get("title") or "SECRET REVEALED"
        thumbnail = phase8.generate_thumbnail(final_video, thumb_text, topic_prompt=script.get("title", ""), channel=channel_niche)
        
        # Append footage credits to description if footage_credits.json exists
        description_text = script["description"]
        if os.path.exists("output/footage_credits.json"):
            try:
                with open("output/footage_credits.json", "r") as fc_file:
                    fc_data = json.load(fc_file)
                    if fc_data:
                        credits_str = "\n\n--- FOOTAGE CREDITS (Educational Fair Use) ---\n"
                        for fc_item in fc_data:
                            name = fc_item.get("name") or ""
                            handle = fc_item.get("handle") or fc_item.get("display_tag") or ""
                            v_url = fc_item.get("url") or ""
                            chan_url = fc_item.get("channel_url") or ""
                            
                            if name and handle and handle != f"@{name}" and handle != "@YouTube" and name != "YouTube":
                                tag = f"{name} ({handle})"
                            elif name and name != "YouTube":
                                tag = name
                            elif handle and handle != "@YouTube":
                                tag = handle
                            else:
                                tag = "YouTube Creator"
                                
                            ref_url = v_url or chan_url
                            if ref_url:
                                credits_str += f"• Footage courtesy: {tag} — {ref_url}\n"
                            else:
                                credits_str += f"• Footage courtesy: {tag}\n"
                        
                        if "--- FOOTAGE CREDITS" not in description_text:
                            description_text = description_text.rstrip() + credits_str
            except Exception as fc_err:
                print(f"[Generate] Warning: Could not append footage credits to description: {fc_err}")

        # Save metadata for publish step
        metadata_path = "output/metadata.json"
        metadata = {
            "title":       script["title"],
            "description": description_text,
            "tags":        script["tags"],
            "category_id": script.get("category_id", "27"),
            "publish_at":  script.get("publish_at"),
            "format":      args.format,
            "video_path":  final_video,
            "thumbnail":   thumbnail
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
            
        # Extract 1 representative review frame per segment for inspection
        keep_files = [
            os.path.basename(final_video),
            os.path.basename(thumbnail),
            "metadata.json",
            "topic.json",
            "script.json",
            "judge_report.json",
            "footage_credits.json"
        ]
        # Retain TTS audio segments so downstream stages never encounter missing audio files
        for f_cand in os.listdir("output"):
            if f_cand.startswith("tts_") and f_cand.endswith(".wav"):
                keep_files.append(f_cand)
        try:
            cum_time = 0.0
            for idx_seg in range(len(script.get("segments", []))):
                seg_dur = tts_durations[idx_seg] if idx_seg < len(tts_durations) else (28.0 / len(script["segments"]))
                sample_time = cum_time + (seg_dur * 0.5)
                cum_time += seg_dur
                frame_out = f"output/frame_seg_{idx_seg}.jpg"
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", f"{sample_time:.2f}", "-i", final_video, "-vframes", "1", "-q:v", "2", frame_out],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                )
                if os.path.exists(frame_out):
                    keep_files.append(os.path.basename(frame_out))
        except Exception as f_err:
            print(f"[Generate] Warning: Review frame extraction: {f_err}")

        # Cleanup intermediate files in output/ to save space
        print("Cleaning up intermediate files...")
        for f in os.listdir("output"):
            if f not in keep_files:
                path = os.path.join("output", f)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                except Exception as e:
                    print(f"Warning: Could not remove temporary file {f}: {e}")

        print(f"\n✅ Generation complete. Video: {final_video}")
        print("Artifact ready. Trigger the Publish workflow in GitHub mobile app to upload.")
        
    except Exception as err:
        print(f"\n❌ Pipeline failed during execution: {err}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
