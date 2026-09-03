import os
import wave
import shutil
import subprocess
import json
import re
from pipeline.sfx import create_sfx_track

def get_wav_duration(filepath: str) -> float:
    with wave.open(filepath, 'rb') as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)

def get_video_duration(filepath: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    try:
        return float(subprocess.check_output(cmd).decode().strip())
    except Exception:
        return 0.0

def assemble_video(broll_files: list[str], tts_files: list[str], captions_ass: str, music_path: str, script: dict, format_type: str) -> str:
    print("Starting video assembly...")
    os.makedirs("output", exist_ok=True)
    
    # Step 1: Normalize all B-roll clips to uniform spec
    print("Step 1: Normalizing B-roll clips...")
    normalized_brolls = []
    durations = []
    ss_offsets = []
    
    w, h = (1080, 1920) if format_type == "short" else (1920, 1080)
    
    footage_credits = []
    seen_handles = set()

    for i, (broll_path, tts_path) in enumerate(zip(broll_files, tts_files)):
        duration = get_wav_duration(tts_path)
        durations.append(duration)
        norm_path = f"output/broll_{i}_norm.mp4"
        
        # Calculate dynamic start offset to skip black screen / intro slides in long videos
        total_dur = get_video_duration(broll_path)
        ss_offset = 0.0
        if total_dur > 30.0:
            # Skip first 20%, up to 30s
            ss_offset = min(30.0, total_dur * 0.2)
        elif total_dur > 15.0:
            # Skip first 3 seconds
            ss_offset = 3.0
        elif total_dur > 8.0:
            ss_offset = 1.0
            
        if ss_offset + duration > total_dur:
            ss_offset = max(0.0, total_dur - duration)
        ss_offsets.append(ss_offset)

    for i, (broll_path, tts_path, seg) in enumerate(zip(broll_files, tts_files, script["segments"])):
        duration = durations[i]
        ss_offset = ss_offsets[i]
        norm_path = f"output/broll_{i}_norm.mp4"
        
        # Handle missing/None broll_path by harvesting real multi-platform footage before image fallback
        if not broll_path or not os.path.exists(broll_path) or os.path.getsize(broll_path) < 10_000:
            broll_path = f"output/emergency_broll_{i}.mp4"
            print(f"[Assemble] B-roll for segment {i} missing. Running MultiPlatformVideoHarvester...")
            seg_info = script.get("segments", [])[i] if script and i < len(script.get("segments", [])) else {}
            seg_narration = seg_info.get("narration") or seg_info.get("broll_query") or "authentic documentary 4k footage"
            seg_query = seg_info.get("broll_query") or seg_info.get("narration") or "cinematic 4k footage" 
            
            video_success = False
            
            # 1. Try MultiPlatformVideoHarvester across YouTube, Reddit, DuckDuckGo, NASA, Archive, TikTok
            try:
                from pipeline.video_harvester_engine import get_video_harvester
                from pipeline.phase4_broll import _download_video_robust, _image_to_ken_burns_video
                harvester = get_video_harvester()
                profile, top_cands = harvester.harvest_for_sentence(seg_narration, niche=script.get("channel", "general"), max_candidates=5)
                for cand in top_cands:
                    temp_vid = f"output/emergency_harv_{i}.mp4"
                    cand_dict = {
                        "video_url": cand.stream_url or cand.url,
                        "duration": cand.duration,
                        "uploader_name": cand.channel_name,
                        "uploader_handle": cand.channel_name
                    }
                    if _download_video_robust(cand.stream_url or cand.url, temp_vid, i, candidate_info=cand_dict):
                        _image_to_ken_burns_video(temp_vid, broll_path, w, h, duration=duration)
                        if os.path.exists(temp_vid):
                            try: os.remove(temp_vid)
                            except Exception: pass
                        if os.path.exists(broll_path) and os.path.getsize(broll_path) > 20_000:
                            video_success = True
                            print(f"[Assemble] Successfully harvested real footage '{cand.title}' for segment {i}!")
                            break
            except Exception as harv_err:
                print(f"[Assemble] Emergency harvester note: {harv_err}")
                
            # 2. Authentic Video Fallback: Strict MultiPlatform Harvester
            # Unrelated stock footage is strictly banned from emergency b-rolls.
            
            # 3. Pollinations 4K motion generator fallback only if all video searches fail
            if not video_success:
                prompt_clean = f"4k cinematic documentary footage of {seg_query}, photorealistic, 8k, detailed, no text, no watermark"
                from pipeline.phase4_broll import _pollinations_image, _image_to_ken_burns_video
                synth_img = f"output/emergency_img_{i}.jpg"
                if _pollinations_image(prompt_clean, synth_img, w=2160, h=3840):
                    _image_to_ken_burns_video(synth_img, broll_path, w, h, duration=duration)
                else:
                    # 4. Authentic Wikimedia/Wikipedia image fallback
                    from pipeline.phase4_broll import _wikimedia_image, _wikipedia_image
                    wiki_img = _wikimedia_image(seg_query) or _wikipedia_image(seg_query) or _wikimedia_image(seg_narration)
                    if wiki_img:
                        try:
                            import requests
                            r_img = requests.get(wiki_img, timeout=15, headers={"User-Agent": "DocuHarvester/2.0"})
                            if r_img.status_code == 200 and len(r_img.content) > 5000:
                                with open(synth_img, "wb") as f_img:
                                    f_img.write(r_img.content)
                                _image_to_ken_burns_video(synth_img, broll_path, w, h, duration=duration)
                                video_success = True
                        except Exception as e_w:
                            print(f"[Assemble] Wikimedia emergency fallback error: {e_w}")

                    if not video_success:
                        # Dark cinematic technical aesthetic instead of neon blue gradient
                        cmd_synth = [
                            "ffmpeg", "-y", "-f", "lavfi",
                            "-i", f"color=c=0x080c14:s={w}x{h}:r=30,drawgrid=w=120:h=120:t=1:c=0x1a2638@0.35,vignette=angle=0.5",
                            "-t", str(duration),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", broll_path
                        ]
                        subprocess.run(cmd_synth, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"Normalizing segment {i} B-roll to duration {duration:.3f}s (offset: {ss_offset:.3f}s)...")

        drawtext_chain = ""
        credit_file = f"output/broll_{i}_credit.json"
        if os.path.exists(credit_file):
            try:
                with open(credit_file, "r") as cf:
                    cdata = json.load(cf)
                    u_name = cdata.get("uploader_name") or ""
                    u_handle = cdata.get("uploader_handle") or ""
                    v_url = cdata.get("video_url") or ""
                    v_title = cdata.get("title") or ""
                    v_chan_url = cdata.get("channel_url") or ""
                    
                    if u_handle and u_handle != "@YouTube":
                        display_tag = u_handle
                    elif u_name and u_name != "YouTube":
                        display_tag = u_name
                    else:
                        display_tag = "@YouTube"
                        
                    credit_key = u_handle if (u_handle and u_handle != "@YouTube") else u_name
                    if credit_key and credit_key not in seen_handles:
                        seen_handles.add(credit_key)
                        footage_credits.append({
                            "name": u_name,
                            "handle": u_handle,
                            "display_tag": display_tag,
                            "url": v_url,
                            "channel_url": v_chan_url,
                            "title": v_title
                        })
                    
                    clean_display = str(display_tag).replace("\\", "").replace("'", "").replace(":", "\\:").replace("%", "\\%")
                    clean_txt = f"Footage\\: {clean_display}"
                    drawtext_chain = f",drawtext=text='{clean_txt}':x=40:y=80:fontsize=24:fontcolor=white:shadowcolor=black@0.85:shadowx=2:shadowy=2:enable='between(t,0,3.5)'"
                    print(f"[Assemble] Burning clean on-screen attribution badge for segment {i}: Footage: {display_tag}")
            except Exception as cerr:
                print(f"[Assemble] Warning: Could not parse credit file {credit_file}: {cerr}")

        # Select randomized cinematic camera motion (Ken Burns / Pan / Zoom)
        import random as _rnd
        motion_idx = _rnd.randint(0, 4)
        
        # Base scale-crop to cover full bleed with unsharp masking for enhanced clarity
        if motion_idx == 0:
            # 1. Slow Cinematic Diagonal Pan Up-Right
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'max(0, min(in_w-out_w, (in_w-out_w)/2 + (t-{duration}/2)*12))':'max(0, min(in_h-out_h, (in_h-out_h)/2 + (t-{duration}/2)*12))',"
                f"eq=contrast=1.06:saturation=1.12:gamma=0.96,unsharp=5:5:0.8:5:5:0.4,vignette=angle=0.4,setsar=1" + drawtext_chain
            )
        elif motion_idx == 1:
            # 2. Slow Panning Upward
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'(in_w-out_w)/2':'max(0, min(in_h-out_h, (in_h-out_h)/2 + (t-{duration}/2)*15))',"
                f"eq=contrast=1.06:saturation=1.12:gamma=0.96,unsharp=5:5:0.8:5:5:0.4,vignette=angle=0.4,setsar=1" + drawtext_chain
            )
        elif motion_idx == 2:
            # 3. Slow Panning Downward
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'(in_w-out_w)/2':'max(0, min(in_h-out_h, (in_h-out_h)/2 - (t-{duration}/2)*15))',"
                f"eq=contrast=1.06:saturation=1.12:gamma=0.96,unsharp=5:5:0.8:5:5:0.4,vignette=angle=0.4,setsar=1" + drawtext_chain
            )
        elif motion_idx == 3:
            # 4. Slow Panning Right
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'max(0, min(in_w-out_w, (in_w-out_w)/2 + (t-{duration}/2)*15))':'(in_h-out_h)/2',"
                f"eq=contrast=1.06:saturation=1.12:gamma=0.96,unsharp=5:5:0.8:5:5:0.4,vignette=angle=0.4,setsar=1" + drawtext_chain
            )
        else:
            # 5. Slow Panning Left
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'max(0, min(in_w-out_w, (in_w-out_w)/2 - (t-{duration}/2)*15))':'(in_h-out_h)/2',"
                f"eq=contrast=1.06:saturation=1.12:gamma=0.96,unsharp=5:5:0.8:5:5:0.4,vignette=angle=0.4,setsar=1" + drawtext_chain
            )
            
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", broll_path,
            "-ss", f"{ss_offset:.3f}", "-t", f"{duration:.3f}",
            "-vf", vf_chain,
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-an", norm_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Verify segment clip has zero black screen before accepting into assembly
        cmd_chk = ["ffmpeg", "-i", norm_path, "-vf", "blackdetect=d=0.5:pix_th=0.10", "-f", "null", "-"]
        res_chk = subprocess.run(cmd_chk, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
        black_durs = [float(d) for d in re.findall(r"black_duration:([0-9.]+)", res_chk.stderr or "")]
        if any(bd > 0.5 for bd in black_durs):
            print(f"[Assemble] Warning: Segment {i} clip has black frames ({max(black_durs):.2f}s). Attempting dynamic time shift on original video...")
            # 1. Try shifting start offset to skip black intro scene
            shift_success = False
            total_dur = get_video_duration(broll_path)
            for shift_sec in [ss_offset + 3.0, ss_offset + 6.0, max(0.0, total_dur * 0.5)]:
                if shift_sec + duration <= total_dur:
                    cmd_shift = [
                        "ffmpeg", "-y", "-stream_loop", "-1", "-i", broll_path,
                        "-ss", f"{shift_sec:.3f}", "-t", f"{duration:.3f}",
                        "-vf", vf_chain,
                        "-r", "30", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-an", norm_path
                    ]
                    subprocess.run(cmd_shift, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    res_shift_chk = subprocess.run(cmd_chk, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
                    shift_black = [float(d) for d in re.findall(r"black_duration:([0-9.]+)", res_shift_chk.stderr or "")]
                    if not any(bd > 0.5 for bd in shift_black):
                        print(f"[Assemble] ✅ Successfully recovered segment {i} real video with offset {shift_sec:.2f}s (zero black frames)!")
                        shift_success = True
                        break
            
            if not shift_success:
                print(f"[Assemble] Shifted time failed to clear black screen. Searching alternative real video candidate...")
                # 2. Try fetching next candidate from YouTube
                seg_info = script.get("segments", [])[i] if script and i < len(script.get("segments", [])) else {}
                seg_query = seg_info.get("broll_query") or seg_info.get("narration") or "cinematic 4k motion"
                alt_success = False
                try:
                    from pipeline.phase4_broll import _youtube_candidates, _download_video_robust, _image_to_ken_burns_video
                    yt_alts = _youtube_candidates(seg_query, n=3)
                    for cand in yt_alts:
                        alt_vid = f"output/alt_vid_{i}.mp4"
                        if _download_video_robust(cand["video_url"], alt_vid, i, candidate_info=cand):
                            _image_to_ken_burns_video(alt_vid, norm_path, w, h, duration=duration)
                            if os.path.exists(alt_vid):
                                try: os.remove(alt_vid)
                                except Exception: pass
                            alt_success = True
                            print(f"[Assemble] ✅ Successfully replaced with alternative YouTube video candidate for segment {i}!")
                            break
                except Exception as e_alt:
                    print(f"[Assemble] Alternative video candidate search note: {e_alt}")

                if not alt_success:
                    print(f"[Assemble] Regenerating segment {i} with clean 4K motion...")
                    prompt_clean = f"4k cinematic documentary footage of {seg_query}, photorealistic, 8k, detailed, no text, no watermark"
                    from pipeline.phase4_broll import _pollinations_image, _image_to_ken_burns_video
                    synth_img = f"output/clean_synth_{i}.jpg"
                    if _pollinations_image(prompt_clean, synth_img, w=2160, h=3840):
                        _image_to_ken_burns_video(synth_img, norm_path, w, h, duration=duration)
                    else:
                        cmd_synth = [
                            "ffmpeg", "-y", "-f", "lavfi",
                            "-i", f"gradients=s={w}x{h}:r=30:c0=0x0a2244:c1=0x00d4ff:c2=0xff007f:x0=0:y0=0:x1={w}:y1={h}:speed=0.01",
                            "-t", str(duration),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", norm_path
                        ]
                        subprocess.run(cmd_synth, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        normalized_brolls.append(norm_path)

    if footage_credits:
        try:
            with open("output/footage_credits.json", "w") as fcf:
                json.dump(footage_credits, fcf, indent=2)
            print(f"[Assemble] Saved {len(footage_credits)} footage credit entries to output/footage_credits.json.")
        except Exception as fc_err:
            print(f"[Assemble] Warning: Could not save footage_credits.json: {fc_err}")

    # Step 2: Concatenate B-roll (no audio)
    print("Step 2: Concatenating B-roll clips...")
    concat_list_path = "output/concat_list.txt"
    with open(concat_list_path, "w") as f:
        for norm_path in normalized_brolls:
            abs_path = os.path.abspath(norm_path)
            f.write(f"file '{abs_path}'\n")
            
    assembled_video_path = "output/assembled_video.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
        "-c", "copy",
        assembled_video_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 3: Concatenate TTS audio segments
    print("Step 3: Concatenating TTS audio segments...")
    audio_list_path = "output/audio_list.txt"
    with open(audio_list_path, "w") as f:
        for tts_path in tts_files:
            abs_path = os.path.abspath(tts_path)
            f.write(f"file '{abs_path}'\n")
            
    tts_combined_path = "output/tts_combined.wav"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", audio_list_path,
        "-c", "copy", tts_combined_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 3b: Create SFX track (whoosh at each clip boundary)
    print("Step 3b: Generating SFX track…")
    total_tts_duration = sum(durations)
    # Clip boundaries are at cumulative TTS durations (skip the first clip — no whoosh at t=0)
    boundary_times = []
    cumulative = 0.0
    for d in durations[:-1]:   # all boundaries except the last (end of video)
        cumulative += d
        boundary_times.append(cumulative)
    sfx_track_path = create_sfx_track(boundary_times, total_tts_duration, topic=script.get("topic", ""))

    # Step 4: Add karaoke captions to video
    print("Step 4: Adding captions...")
    assembled_capped_path = "output/assembled_capped.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", assembled_video_path,
        "-vf", f"ass='{captions_ass}'",
        "-c:v", "libx264", "-preset", "superfast", "-crf", "18", "-pix_fmt", "yuv420p",
        assembled_capped_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 5: Clean cinematic finishing pass (clean passthrough, zero text slop or strobe boxes)
    print("Step 5: Clean video finishing pass...")
    assembled_flashed_path = assembled_capped_path

    # Step 6: Final mix: video + TTS + music + SFX
    print("Step 6: Final audio mix with SFX…")
    final_output_path = f"output/final_{format_type}.mp4"

    filter_complex = (
        "[1:a]highpass=f=80,volume=2.2,asplit=2[tts1][tts2];"
        # Background music sits gently at -22dB baseline so it never competes with speech
        "[2:a]volume=0.08,aloop=loop=-1:size=2147483647[music_loop];"
        "[3:a]volume=0.18[sfx];"
        # Deep sidechain ducking: voice instantly drops music by additional -10dB (threshold=0.03, ratio=8)
        "[music_loop][tts1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[music_ducked];"
        "[tts2][music_ducked]amix=inputs=2:duration=first:normalize=0[mixed];"
        "[mixed][sfx]amix=inputs=2:duration=first:normalize=0[premix];"
        "[premix]loudnorm=I=-14:TP=-1.5:LRA=11[audio_final]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", assembled_flashed_path,
        "-i", tts_combined_path,
        "-i", music_path,
        "-i", sfx_track_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[audio_final]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart",
        final_output_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"Assembly completed. Final video: {final_output_path}")
    return final_output_path
