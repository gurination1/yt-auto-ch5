import argparse
import json
import os
import sys
import google.auth.exceptions
import pipeline.phase9_upload as phase9

def main():
    parser = argparse.ArgumentParser(description="yt-auto Video Publisher")
    parser.add_argument("--bypass-judge", action="store_true", help="Bypass the Judge AI visual check")
    args = parser.parse_args()
    
    metadata_path = "output/metadata.json"
    if not os.path.exists(metadata_path):
        print(f"Error: Metadata file not found at {metadata_path}. Have you run generation first?")
        sys.exit(1)
        
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
        
    # Extract format and files
    fmt = metadata.get("format", "short")
    video_path = metadata.get("video_path")
    thumbnail_path = metadata.get("thumbnail")
    
    # Resilient path check: if the absolute path from generation doesn't exist,
    # look in the local output/ folder
    if not video_path or not os.path.exists(video_path):
        fallback_video = f"output/final_{fmt}.mp4"
        if os.path.exists(fallback_video):
            video_path = fallback_video
        else:
            print(f"Error: Video file not found. Checked: {video_path} and {fallback_video}")
            sys.exit(1)
            
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        fallback_thumb = "output/thumbnail.jpg"
        if os.path.exists(fallback_thumb):
            thumbnail_path = fallback_thumb
        else:
            print(f"Error: Thumbnail file not found. Checked: {thumbnail_path} and {fallback_thumb}")
            sys.exit(1)

    # --- STRICT BLACK-SCREEN VERIFICATION CHECK ---
    import subprocess
    import re
    print(f"\n🔍 Running strict FFmpeg black-screen verification on {video_path}...")
    cmd_chk = ["ffmpeg", "-i", video_path, "-vf", "blackdetect=d=0.8:pic_th=0.99:pix_th=0.03", "-f", "null", "-"]
    res_chk = subprocess.run(cmd_chk, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
    black_durations = [float(d) for d in re.findall(r"black_duration:([0-9.]+)", res_chk.stderr or "")]
    if any(bd > 0.8 for bd in black_durations):
        max_bd = max(black_durations)
        print(f"\n❌ CRITICAL UPLOAD BLOCKED! Black screen section detected ({max_bd:.2f}s > 0.8s) in {video_path}!")
        print("Upload to YouTube has been BLOCKED to prevent bad video publishing.")
        sys.exit(1)
    else:
        print("✅ Strict black-screen verification PASSED! Zero black screens detected.\n")
    if not args.bypass_judge:
        print("\n⚖️ Initiating Judge AI visual and narrative check...")
        
        # Check if we already have a cached report from the generation phase
        report_path = "output/judge_report.json"
        report = None
        if os.path.exists(report_path):
            try:
                with open(report_path, "r") as rf:
                    report = json.load(rf)
                print("Found cached Judge AI report from generation phase. Reusing report...")
            except Exception as e:
                print(f"Warning: Failed to load cached judge report: {e}. Running full review...")
                
        if not report:
            from pipeline.judge import JudgeClient

            judge = JudgeClient()
            try:
                report = judge.review_video(video_path, metadata)
                # Save the judge report
                with open(report_path, "w") as rf:
                    json.dump(report, rf, indent=2)
            except Exception as judge_err:
                print(f"Error: Judge AI review encountered an error: {judge_err}.")
                print("Blocking upload to prevent unverified video publishing.")
                report = {"status": "REJECTED", "score": 50, "reason": f"Bypassed due to Judge API error: {judge_err}"}
                
        status = report.get("status", "REJECTED")
        score = int(report.get("score", 0) or 0)
        cohesiveness = int(report.get("cohesiveness_score", 100) or 0)
        failed_segs = report.get("failed_segments", [])
        reason = report.get("reason", "No reason provided")
        issues = report.get("issues", [])
        
        if status != "PASSED" or score < 85 or cohesiveness < 75 or (isinstance(failed_segs, list) and len(failed_segs) > 0):
            print("\n🛑 VIDEO REJECTED BY JUDGE AI!")
            print(f"Score: {score}/100 | Cohesiveness: {cohesiveness}/100 | Status: {status}")
            if failed_segs:
                print(f"Failed Segments: {failed_segs}")
            print(f"Reason: {reason}")
            if issues:
                print("Issues:")
                for issue in issues:
                    print(f" - {issue}")
            print("\nFix the issues and regenerate the video before publishing.")
            sys.exit(1)
        else:
            print(f"\n✅ Video PASSED Judge AI review! (Score: {score}/100 | Cohesiveness: {cohesiveness}/100)")
            print(f"Judge Comments: {reason}\n")
    else:
        print("\n⚠️ Bypassing Judge AI check as requested.")
            
    print(f"Publishing {fmt} video...")
    print(f"Video: {video_path}")
    print(f"Thumbnail: {thumbnail_path}")
    print(f"Title: {metadata.get('title')}")
    
    # --- FOOTAGE CREDITS ATTRIBUTION APPEND ---
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
                    
                    curr_desc = metadata.get("description", "") or ""
                    if "--- FOOTAGE CREDITS" not in curr_desc:
                        metadata["description"] = curr_desc.rstrip() + credits_str
                        print(f"[Publish] Appended {len(fc_data)} footage credit entries to video description.")
        except Exception as fc_err:
            print(f"[Publish] Warning: Could not append footage credits: {fc_err}")

    # --- DECOUPLED PLATFORM UPLOADS ---
    print("\n🚀 Starting platform uploads...")
    
    if os.environ.get("DISABLE_YT_UPLOAD") == "1":
        print("\n⏸️ DISABLE_YT_UPLOAD=1 is set. Skipping direct YouTube upload to allow manual video verification.")
        print("✅ Pre-upload verification & video generation complete. Video artifact saved successfully!")
        sys.exit(0)
    
    published_results = {
        "title": metadata.get("title"),
        "youtube": None,
        "dailymotion": None,
        "rumble": None,
        "facebook": None,
        "instagram": None,
        "threads": None
    }
    
    # 1. YouTube Upload
    yt_success = False
    try:
        print("\n📺 Initiating YouTube upload...")
        video_id = phase9.upload_to_youtube(video_path, thumbnail_path, metadata)
        print(f"✅ Successfully published to YouTube! Video ID: {video_id}")
        print(f"Direct Link: https://www.youtube.com/watch?v={video_id}")
        print(f"Short Link: https://www.youtube.com/shorts/{video_id}")
        print(f"Unmasked YouTube ID chars: {list(video_id)}")
        published_results["youtube"] = {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "short_url": f"https://www.youtube.com/shorts/{video_id}"
        }
        yt_success = True
    except google.auth.exceptions.RefreshError as ref_err:
        print("\n⚠️ YouTube Authentication Error: Refresh token may have expired or is invalid.")
        print("Re-generate your refresh token at: https://developers.google.com/oauthplayground")
        print(f"Details: {ref_err}")
    except Exception as e:
        print(f"⚠️ YouTube upload failed with error: {e}")
        
    if not yt_success:
        print("⚠️ YouTube upload did not complete. Continuing with other platform uploads...")
        
    # 2. Dailymotion Upload
    try:
        print("\n🚀 Initiating Dailymotion upload...")
        import importlib
        phase10 = importlib.import_module("pipeline.phase10_dailymotion")
        dm_id = phase10.upload_to_dailymotion(video_path, metadata)
        if dm_id:
            print(f"✅ Successfully published to Dailymotion! Video ID: {dm_id}")
            published_results["dailymotion"] = {
                "video_id": dm_id,
                "url": f"https://www.dailymotion.com/video/{dm_id}"
            }
    except Exception as dm_err:
        print(f"⚠️ Warning: Dailymotion upload encountered an error: {dm_err}")

    # 3. Rumble Upload
    try:
        print("\n🚀 Initiating Rumble upload...")
        import importlib
        phase11 = importlib.import_module("pipeline.phase11_rumble")
        rumble_url = phase11.upload_to_rumble(video_path, metadata)
        if rumble_url:
            print(f"✅ Successfully published to Rumble! URL: {rumble_url}")
            published_results["rumble"] = {
                "url": rumble_url
            }
    except Exception as rb_err:
        print(f"⚠️ Warning: Rumble upload encountered an error: {rb_err}")

    # 4. Meta (Facebook + Instagram) Upload
    try:
        print("\n🚀 Initiating Meta (Facebook + Instagram) upload...")
        import importlib
        phase12 = importlib.import_module("pipeline.phase12_meta")
        meta_result = phase12.upload_to_meta(video_path, metadata)
        if meta_result.get("fb_video_id"):
            print(f"✅ Facebook Reel published! ID: {meta_result['fb_video_id']}")
            published_results["facebook"] = meta_result["fb_video_id"]
        if meta_result.get("ig_media_id"):
            print(f"✅ Instagram Reel published! ID: {meta_result['ig_media_id']}")
            published_results["instagram"] = meta_result["ig_media_id"]
    except Exception as meta_err:
        print(f"⚠️ Warning: Meta upload encountered an error: {meta_err}")

    # 5. Threads Upload
    try:
        print("\n🚀 Initiating Threads upload...")
        threads_user_id = os.environ.get("THREADS_USER_ID") or ""
        threads_token = os.environ.get("THREADS_ACCESS_TOKEN") or ""
        
        if threads_user_id and threads_token:
            import importlib
            phase13 = importlib.import_module("pipeline.phase13_threads")
            
            # Build Threads caption
            title = metadata.get("title", "")
            hashtags_list = []
            tags = metadata.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            elif isinstance(tags, list):
                pass
            else:
                tags = []
                
            for tag in tags:
                clean_tag = "".join(c for c in tag if c.isalnum())
                if clean_tag:
                    hashtags_list.append(f"#{clean_tag.lower()}")
                    
            desc = metadata.get("description", "")
            for word in desc.split():
                if word.startswith("#"):
                    clean_h = "#" + "".join(c for c in word if c.isalnum())
                    if clean_h != "#" and clean_h.lower() not in [h.lower() for h in hashtags_list]:
                        hashtags_list.append(clean_h.lower())
                        
            threads_hashtags = " ".join(hashtags_list)
            threads_caption = f"{title}\n\n📲 Link in bio!\n\n{threads_hashtags}"
            threads_caption = threads_caption[:500]
            
            threads_post_id = phase13.upload_to_threads(video_path, threads_caption, threads_user_id, threads_token)
            if threads_post_id:
                print(f"✅ Threads post published! ID: {threads_post_id}")
                published_results["threads"] = threads_post_id
        else:
            print("[Threads] Skipped — THREADS_USER_ID or THREADS_ACCESS_TOKEN not set.")
    except Exception as threads_err:
        print(f"⚠️ Warning: Threads upload encountered an error: {threads_err}")

    # Write published results to disk
    os.makedirs("output", exist_ok=True)
    with open("output/published_urls.json", "w") as pf:
        json.dump(published_results, pf, indent=2)
    print("\n📄 Publication results saved to output/published_urls.json")

    # Render GitHub Step Summary if running in Actions
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        try:
            with open(step_summary, "a") as sf:
                sf.write(f"\n## 🚀 Published Social Media Links\n\n")
                if published_results.get("youtube"):
                    yt_data = published_results["youtube"]
                    sf.write(f"- 📺 **YouTube Short**: [{metadata.get('title')}]({yt_data['short_url']})\n")
                    sf.write(f"- 🔗 **Direct URL**: {yt_data['url']}\n")
                if published_results.get("dailymotion"):
                    dm_data = published_results["dailymotion"]
                    sf.write(f"- 🎬 **Dailymotion**: [{dm_data['video_id']}]({dm_data['url']})\n")
                if published_results.get("rumble"):
                    rb_data = published_results["rumble"]
                    sf.write(f"- ⚡ **Rumble**: [{rb_data['url']}]({rb_data['url']})\n")
                if published_results.get("facebook"):
                    sf.write(f"- 📘 **Facebook Reel ID**: `{published_results['facebook']}`\n")
                if published_results.get("instagram"):
                    sf.write(f"- 📸 **Instagram Reel ID**: `{published_results['instagram']}`\n")
                if published_results.get("threads"):
                    sf.write(f"- 🧵 **Threads Post ID**: `{published_results['threads']}`\n")
        except Exception as se:
            print(f"Warning: Could not write GITHUB_STEP_SUMMARY: {se}")

if __name__ == "__main__":
    main()
