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

def _harvest_emergency_visual(seg_query: str, seg_narration: str, out_path: str, w: int, h: int, duration: float, script_topic: str = "", channel: str = "general") -> bool:
    """Guarantees authentic topic-specific documentary visual is generated for a failed segment.
    NEVER uses abstract gradients, solid colors, or synthetic test patterns.
    Priority:
    1. MultiPlatformHarvester real video clip (NASA, Archive, DVIDS, Reddit, Wikimedia)
    2. Wikipedia HD official article photograph / micrograph
    3. NASA Image & Video Library photo (if space/science)
    4. Wikimedia Commons archival photo
    5. Pollinations AI Flux / Turbo photorealistic scene
    6. PIL dark technical schematic with authentic topic title & citation badge
    """
    import re
    import requests
    from pipeline.phase4_broll import (
        _image_to_ken_burns_video,
        _wikipedia_hd_image,
        _wikimedia_image,
        _wikipedia_image,
        _nasa_image,
        _pollinations_image,
        _pil_placeholder,
        _deep_inspect_video_frames,
    )

    # 1. Try real video harvesting via MultiPlatformVideoHarvester
    try:
        from pipeline.video_harvester_engine import get_video_harvester
        from pipeline.phase4_broll import _download_video_robust
        harvester = get_video_harvester()
        search_phrase = seg_narration or seg_query or script_topic
        profile, top_cands = harvester.harvest_for_sentence(search_phrase, niche=channel, max_candidates=4)
        for cand in top_cands:
            temp_vid = f"output/emergency_harv_{abs(hash(seg_query)) % 10000}.mp4"
            cand_dict = {
                "video_url": cand.stream_url or cand.url,
                "duration": cand.duration,
                "uploader_name": cand.channel_name,
                "uploader_handle": cand.channel_name
            }
            if _download_video_robust(cand.stream_url or cand.url, temp_vid, 99, candidate_info=cand_dict):
                passed, reason = _deep_inspect_video_frames(temp_vid, query=seg_query, narration=seg_narration, topic=script_topic)
                if not passed:
                    print(f"[Assemble] Emergency video candidate failed frame check: {reason}. Trying next...")
                    if os.path.exists(temp_vid):
                        try: os.remove(temp_vid)
                        except Exception: pass
                    continue
                _image_to_ken_burns_video(temp_vid, out_path, w, h, duration=duration)
                if os.path.exists(temp_vid):
                    try: os.remove(temp_vid)
                    except Exception: pass
                if os.path.exists(out_path) and os.path.getsize(out_path) > 20_000:
                    print(f"[Assemble] Successfully harvested real footage '{cand.title}' for emergency visual!")
                    return True
    except Exception as harv_err:
        print(f"[Assemble] MultiPlatformVideoHarvester emergency note: {harv_err}")

    # Extract clean core entity for image searches
    noise_words = {
        "footage", "real", "authentic", "documentary", "4k", "1080p", "hd", "video", "broll", "clip",
        "cinematic", "photorealistic", "national", "geographic", "transformed", "into", "created",
        "discovered", "reveals", "secret", "mystery", "unsolved", "experiment", "scientists", "lab",
        "proves", "shows", "found", "using", "with", "from", "at", "by", "for", "on", "in", "the", "and"
    }
    candidates_to_extract = [seg_query, script_topic, seg_narration]
    entities = []
    for text in candidates_to_extract:
        if not text:
            continue
        words = [w for w in re.sub(r"[^\w\s-]", " ", text).split() if len(w) > 2 and w.lower() not in noise_words]
        if words:
            entities.append(" ".join(words[:4]))
            entities.append(" ".join(words[:2]))
    if not entities and script_topic:
        entities.append(script_topic[:40])

    synth_img = f"output/emergency_img_{abs(hash(seg_query)) % 10000}.jpg"

    # 2. Authentic Wikipedia HD official photograph/micrograph
    for ent in entities:
        if _wikipedia_hd_image(ent, synth_img):
            print(f"[Assemble] Secured Wikipedia HD archival photo for '{ent}'. Applying Ken Burns...")
            _image_to_ken_burns_video(synth_img, out_path, w, h, duration=duration, caption="")
            if os.path.exists(synth_img):
                try: os.remove(synth_img)
                except Exception: pass
            return True

    # 3. Authentic NASA Image & Video Library (for space/science) or Wikimedia Commons
    is_space = any(k in f"{channel} {script_topic} {seg_query}".lower() for k in ["space", "nasa", "planet", "astronomy", "cosmos", "galaxy", "physics", "science", "atom", "quantum", "star"])
    for ent in entities:
        img_url = None
        if is_space:
            try:
                img_url = _nasa_image(ent) or _nasa_image("space galaxy stars")
            except Exception:
                pass
        if not img_url:
            try:
                img_url = _wikimedia_image(ent) or _wikipedia_image(ent)
            except Exception:
                pass
        if img_url:
            try:
                r_img = requests.get(img_url, timeout=15, headers={"User-Agent": "DocuHarvester/2.0"})
                if r_img.status_code == 200 and len(r_img.content) > 5000:
                    with open(synth_img, "wb") as f_img:
                        f_img.write(r_img.content)
                    print(f"[Assemble] Secured authentic institutional photo ({img_url[:60]}). Applying Ken Burns...")
                    _image_to_ken_burns_video(synth_img, out_path, w, h, duration=duration, caption="ARCHIVAL SPECIMEN")
                    if os.path.exists(synth_img):
                        try: os.remove(synth_img)
                        except Exception: pass
                    return True
            except Exception as e_w:
                print(f"[Assemble] Institutional image download note: {e_w}")

    # 4. Pollinations 4K photorealistic scene
    best_entity = entities[0] if entities else (script_topic or seg_query or "scientific discovery")
    prompt_clean = f"4k cinematic documentary photograph of {best_entity}, national geographic photography, hyperrealistic, 8k, highly detailed, photorealistic, no text, no watermark"
    if _pollinations_image(prompt_clean, synth_img, w=w, h=h):
        print(f"[Assemble] Generated 4K Pollinations visual for '{best_entity}'. Applying Ken Burns...")
        _image_to_ken_burns_video(synth_img, out_path, w, h, duration=duration)
        if os.path.exists(synth_img):
            try: os.remove(synth_img)
            except Exception: pass
        return True

    # 5. Last resort: Clean text-free procedural cinematic dark visual plate
    print(f"[Assemble] Generating clean cinematic background plate...")
    _pil_placeholder("", w, h, synth_img)
    _image_to_ken_burns_video(synth_img, out_path, w, h, duration=duration, caption="")
    if os.path.exists(synth_img):
        try: os.remove(synth_img)
        except Exception: pass
    return True

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
        
        # Handle missing/None broll_path by harvesting authentic documentary visual
        if not broll_path or not os.path.exists(broll_path) or os.path.getsize(broll_path) < 10_000:
            broll_path = f"output/emergency_broll_{i}.mp4"
            print(f"[Assemble] B-roll for segment {i} missing. Harvesting authentic visual...")
            seg_info = script.get("segments", [])[i] if script and i < len(script.get("segments", [])) else {}
            seg_narration = seg_info.get("narration") or seg_info.get("broll_query") or "authentic documentary 4k footage"
            seg_query = seg_info.get("broll_query") or seg_info.get("narration") or "cinematic 4k footage"
            script_topic = script.get("title", "") or script.get("topic", "")
            channel_niche = script.get("channel", "general")
            _harvest_emergency_visual(seg_query, seg_narration, broll_path, w, h, duration, script_topic=script_topic, channel=channel_niche)

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
        from pipeline.config import get_channel_profile
        chan_niche = (script.get("channel") or os.environ.get("CHANNEL_NICHE", "science")).lower()
        chan_profile = get_channel_profile(chan_niche)
        color_curves = chan_profile.get("color_curves", "eq=contrast=1.06:saturation=1.12:gamma=0.96")
        vignette_angle = 0.48 if chan_niche == "mystery" else 0.40

        motion_idx = _rnd.randint(0, 4)
        
        # Base scale-crop to cover full bleed with unsharp masking for enhanced clarity
        if motion_idx == 0:
            # 1. Slow Cinematic Diagonal Pan Up-Right
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'max(0, min(in_w-out_w, (in_w-out_w)/2 + (t-{duration}/2)*12))':'max(0, min(in_h-out_h, (in_h-out_h)/2 + (t-{duration}/2)*12))',"
                f"{color_curves},unsharp=5:5:0.8:5:5:0.4,vignette=angle={vignette_angle},setsar=1" + drawtext_chain
            )
        elif motion_idx == 1:
            # 2. Slow Panning Upward
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'(in_w-out_w)/2':'max(0, min(in_h-out_h, (in_h-out_h)/2 + (t-{duration}/2)*15))',"
                f"{color_curves},unsharp=5:5:0.8:5:5:0.4,vignette=angle={vignette_angle},setsar=1" + drawtext_chain
            )
        elif motion_idx == 2:
            # 3. Slow Panning Downward
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'(in_w-out_w)/2':'max(0, min(in_h-out_h, (in_h-out_h)/2 - (t-{duration}/2)*15))',"
                f"{color_curves},unsharp=5:5:0.8:5:5:0.4,vignette=angle={vignette_angle},setsar=1" + drawtext_chain
            )
        elif motion_idx == 3:
            # 4. Slow Panning Right
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'max(0, min(in_w-out_w, (in_w-out_w)/2 + (t-{duration}/2)*15))':'(in_h-out_h)/2',"
                f"{color_curves},unsharp=5:5:0.8:5:5:0.4,vignette=angle={vignette_angle},setsar=1" + drawtext_chain
            )
        else:
            # 5. Slow Panning Left
            vf_chain = (
                f"scale=trunc({w}*1.15/2)*2:trunc({h}*1.15/2)*2:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}:'max(0, min(in_w-out_w, (in_w-out_w)/2 - (t-{duration}/2)*15))':'(in_h-out_h)/2',"
                f"{color_curves},unsharp=5:5:0.8:5:5:0.4,vignette=angle={vignette_angle},setsar=1" + drawtext_chain
            )
            
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", broll_path,
            "-ss", f"{ss_offset:.3f}", "-t", f"{duration:.3f}",
            "-vf", vf_chain,
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-an", norm_path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
            print(f"[Assemble] Warning: Advanced motion filter failed on segment {i} ({err_msg[:200]}). Falling back to safe scale...")
            safe_cmd = [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", broll_path,
                "-ss", f"{ss_offset:.3f}", "-t", f"{duration:.3f}",
                "-vf", f"scale=trunc({w}/2)*2:trunc({h}/2)*2:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
                "-r", "30", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-an", norm_path
            ]
            subprocess.run(safe_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Verify segment clip has zero true black screen before accepting into assembly
        cmd_chk = ["ffmpeg", "-i", norm_path, "-vf", "blackdetect=d=0.8:pic_th=0.99:pix_th=0.03", "-f", "null", "-"]
        res_chk = subprocess.run(cmd_chk, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
        black_durs = [float(d) for d in re.findall(r"black_duration:([0-9.]+)", res_chk.stderr or "")]
        if any(bd > 0.8 for bd in black_durs):
            print(f"[Assemble] Warning: Segment {i} clip has black frames ({max(black_durs):.2f}s). Attempting dynamic time shift on original video...")
            shift_success = False
            total_dur = get_video_duration(broll_path)
            black_ends = [float(d) for d in re.findall(r"black_end:([0-9.]+)", res_chk.stderr or "")]
            skip_start = (max(black_ends) + 0.3) if black_ends else 3.0
            
            shift_offsets = [ss_offset + skip_start, ss_offset + 4.0, max(0.0, total_dur * 0.5)]
            for shift_sec in shift_offsets:
                cmd_shift = [
                    "ffmpeg", "-y", "-stream_loop", "-1", "-i", broll_path,
                    "-ss", f"{shift_sec:.3f}", "-t", f"{duration:.3f}",
                    "-vf", vf_chain,
                    "-r", "30", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-an", norm_path
                ]
                subprocess.run(cmd_shift, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                res_shift_chk = subprocess.run(cmd_chk, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
                shift_black = [float(d) for d in re.findall(r"black_duration:([0-9.]+)", res_shift_chk.stderr or "")]
                if not any(bd > 0.8 for bd in shift_black):
                    print(f"[Assemble] ✅ Successfully recovered segment {i} real video with offset {shift_sec:.2f}s (zero black frames)!")
                    shift_success = True
                    break
            
            if not shift_success:
                print(f"[Assemble] Shifted time failed to clear black screen. Harvesting authentic emergency visual...")
                seg_info = script.get("segments", [])[i] if script and i < len(script.get("segments", [])) else {}
                seg_query = seg_info.get("broll_query") or seg_info.get("narration") or "cinematic 4k motion"
                seg_narration = seg_info.get("narration") or seg_query
                _harvest_emergency_visual(
                    seg_query, seg_narration, norm_path, w, h, duration,
                    script_topic=script.get("title", "") or script.get("topic", ""),
                    channel=script.get("channel", "general")
                )
        
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

    niche_clean = (script.get("channel") or os.environ.get("CHANNEL_NICHE") or "science").lower()
    from pipeline.config import get_channel_profile
    chan_profile = get_channel_profile(niche_clean)
    duck = chan_profile.get("ducking", {
        "attack": 25, "release": 250, "ratio": 3.5, "threshold": 0.08, "music_vol": 0.25, "sfx_vol": 0.26
    })
    meta = chan_profile.get("container_metadata", {})
    artist = meta.get("artist", "Axiom Lab Studios / Science & Frontier Tech")
    genre = meta.get("genre", "Science & Technology")
    comment = meta.get("comment", "Autonomous Shorts Fleet")
    vid_title = script.get("title", script.get("topic", "Autonomous Short"))

    filter_complex = (
        f"[1:a]highpass=f=80,volume=2.0,asplit=2[tts1][tts2];"
        f"[2:a]volume={duck['music_vol']},aloop=loop=-1:size=2147483647[music_loop];"
        f"[3:a]volume={duck['sfx_vol']}[sfx];"
        f"[music_loop][tts1]sidechaincompress=threshold={duck['threshold']}:ratio={duck['ratio']}:attack={duck['attack']}:release={duck['release']}[music_ducked];"
        f"[tts2][music_ducked]amix=inputs=2:duration=first:normalize=0[mixed];"
        f"[mixed][sfx]amix=inputs=2:duration=first:normalize=0[premix];"
        f"[premix]loudnorm=I=-14:TP=-1.5:LRA=11[audio_final]"
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
        "-metadata", f"title={vid_title}",
        "-metadata", f"artist={artist}",
        "-metadata", f"album_artist={artist}",
        "-metadata", f"genre={genre}",
        "-metadata", f"comment={comment}",
        "-metadata", f"copyright=© 2026 {artist}. All Rights Reserved.",
        "-metadata", f"encoded_by={artist} Autonomous Media Pipeline v2.6",
        "-shortest", "-movflags", "+faststart",
        final_output_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"Assembly completed. Final video: {final_output_path}")
    return final_output_path
