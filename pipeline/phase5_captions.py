import os
import re
import soundfile as sf
import subprocess
from typing import List, Dict, Any

POWER_WORDS = {
    "TRUTH", "SECRET", "SHOCKING", "DANGEROUS", "CRITICAL", "BRUTAL", "SURPRISING",
    "REVEALED", "WARNING", "CAUTION", "ACCIDENT", "CRASH", "SAFE", "SAFETY",
    "IMPOSSIBLE", "MYSTERY", "KILL", "DIED", "ALIVE", "DEATH", "BANNED",
    "PROVEN", "HIDDEN", "DESTROYED", "BREAKTHROUGH", "DISCOVERY", "UNCOVERED",
    "LIE", "LIES", "TWICE", "EXPLODED", "BRAINS", "SUPERPOWER", "HOT", "ANOMALY"
}

def fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def align_words(script_words: List[str], whisper_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    aligned = []
    ns = len(script_words)
    nw = len(whisper_words)
    if ns == 0 or nw == 0:
        return []
        
    w_idx = 0
    for s_idx, s_word in enumerate(script_words):
        best_w_idx = w_idx
        best_score = 0
        for candidate_idx in range(max(0, w_idx - 4), min(nw, w_idx + 15)):
            w_word = whisper_words[candidate_idx]["text"].strip(".,!?\"'()").upper()
            s_word_clean = s_word.strip(".,!?\"'()").upper()
            if w_word == s_word_clean:
                score = 3
            elif w_word in s_word_clean or s_word_clean in w_word:
                score = 2
            else:
                score = 0
            if score > best_score:
                best_score = score
                best_w_idx = candidate_idx
        if best_score > 0:
            w_idx = best_w_idx
        clamped_w_idx = min(max(0, w_idx), nw - 1)
        aligned.append({
            "word": s_word,
            "start": whisper_words[clamped_w_idx]["start"],
            "end": whisper_words[clamped_w_idx]["end"]
        })
        w_idx = clamped_w_idx + 1
    return aligned

def generate_captions(audio_files: List[str], script: Dict[str, Any], format_type: str = "short") -> str:
    """
    2026 Kinetic Subtitle Engine:
    - 2-3 word retention clustering (MrBeast / Hormozi style)
    - Active word Neon Pop Highlight with elastic bounce
    - High contrast solid black outline stroke
    - Mobile UI safe margin alignment
    """
    if format_type == "short":
        play_res_x = 1080
        play_res_y = 1920
        font_size  = 96      # Ultra-readable mobile size
        margin_v   = 440     # Positioned safely above YouTube Shorts bottom UI
        max_chunk_words = 3
    else:
        play_res_x = 1920
        play_res_y = 1080
        font_size  = 64
        margin_v   = 140
        max_chunk_words = 5

    # ASS Color Palettes (&HAABBGGRR&)
    C_WHITE  = "&H00FFFFFF&"
    C_ACTIVE = "&H0000E6FF&"      # Neon Yellow / Gold (BGR: FF E6 00)
    C_POWER  = "&H0066FF00&"      # Neon Lime / Toxic Green (BGR: 00 FF 66)
    C_DIM    = "&H00D0D0D0&"      # Soft White

    pos_x = play_res_x // 2
    pos_y = play_res_y - margin_v
    pos_tag = f"{{\\an5\\pos({pos_x},{pos_y})}}"

    ass_events = []
    time_offset = 0.0

    model = None
    try:
        from faster_whisper import WhisperModel
        print("Loading faster-whisper 'base' model on CPU...")
        model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=1, num_workers=1)
    except Exception as model_err:
        print(f"Warning: Could not load faster-whisper model ({model_err}). Will use rule-based timing.")

    for i, (audio_path, seg) in enumerate(zip(audio_files, script.get("segments", []))):
        if not os.path.exists(audio_path):
            print(f"Warning: Audio file missing: {audio_path}. Generating fallback audio...")
            try:
                from gtts import gTTS
                tts = gTTS(text=seg["narration"], lang='en')
                temp_mp3 = f"output/temp_missing_{i}.mp3"
                tts.save(temp_mp3)
                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_mp3, "-ac", "1", "-ar", "24000", audio_path],
                    capture_output=True, check=True
                )
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
            except Exception as e:
                print(f"Failed to generate fallback TTS for missing {audio_path}: {e}")

        # Duration detection
        duration = 5.0
        try:
            data, sr = sf.read(audio_path)
            duration = len(data) / sr
        except Exception as sf_err:
            try:
                res = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                    capture_output=True, text=True, check=True
                )
                duration = float(res.stdout.strip())
            except Exception:
                print(f"Warning: Could not read duration for {audio_path} ({sf_err}). Defaulting to 5.0s.")

        script_words = seg["narration"].split()
        aligned_words = []

        if model is not None:
            try:
                print(f"Transcribing TTS file: {audio_path}...")
                segments_out, info = model.transcribe(audio_path, word_timestamps=True)
                whisper_words = []
                for whisper_seg in segments_out:
                    if whisper_seg.words:
                        for word_info in whisper_seg.words:
                            w_text = word_info.word.strip()
                            if w_text:
                                whisper_words.append({
                                    "text": w_text,
                                    "start": word_info.start,
                                    "end": word_info.end
                                })
                aligned_words = align_words(script_words, whisper_words)
            except Exception as seg_err:
                print(f"Warning: Whisper failed for segment {seg.get('id', i)} ({seg_err}). Using rule-based timing.")

        # Fallback to even distribution if Whisper was unavailable
        if not aligned_words and script_words:
            word_dur = duration / len(script_words)
            for w_idx, word in enumerate(script_words):
                aligned_words.append({
                    "word": word,
                    "start": w_idx * word_dur,
                    "end": (w_idx + 1) * word_dur
                })

        # Apply global time offset
        for w in aligned_words:
            w["start"] += time_offset
            w["end"] += time_offset

        # Group words into 2-3 word retention clusters
        chunks = []
        cur_chunk = []
        for w in aligned_words:
            cur_chunk.append(w)
            if len(cur_chunk) >= max_chunk_words or w["word"].endswith((".", "!", "?")):
                chunks.append(cur_chunk)
                cur_chunk = []
        if cur_chunk:
            chunks.append(cur_chunk)

        # Generate Active Word Karaoke Dialogue lines
        for chunk in chunks:
            for act_idx, act_word in enumerate(chunk):
                start_t = act_word["start"]
                end_t = act_word["end"]
                if end_t <= start_t:
                    end_t = start_t + 0.25

                dur_ms = int((end_t - start_t) * 1000)
                pop_ms = min(60, max(25, int(dur_ms * 0.35)))
                settle_ms = min(130, max(60, dur_ms))

                line_parts = []
                for idx, item in enumerate(chunk):
                    raw_w = item["word"].upper()
                    clean_w = raw_w.strip(".,!?\"'()")

                    if idx == act_idx:
                        # Highlight active word with scale pop
                        highlight_c = C_POWER if clean_w in POWER_WORDS else C_ACTIVE
                        part = (
                            f"{{\\c{highlight_c}\\fscx92\\fscy92"
                            f"\\t(0,{pop_ms},1.3,\\fscx120\\fscy120)"
                            f"\\t({pop_ms},{settle_ms},0.8,\\fscx100\\fscy100)}}"
                            f"{raw_w}{{\\r}}"
                        )
                    else:
                        # Inactive word
                        part = f"{{\\c{C_WHITE}\\fscx100\\fscy100}}{raw_w}{{\\r}}"
                    line_parts.append(part)

                full_text = " ".join(line_parts)
                ass_events.append(f"Dialogue: 0,{fmt_time(start_t)},{fmt_time(end_t)},Default,,0,0,0,,{pos_tag}{full_text}")

        time_offset += duration
        print(f"Segment {seg.get('id', i)} duration: {duration:.2f}s, Cumulative offset: {time_offset:.2f}s")

    picked_font = "Bebas Neue"
    ass_header = f"""[Script Info]
Title: 2026 Kinetic Shorts Typography
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{picked_font},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,10,3,5,30,30,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    os.makedirs("output", exist_ok=True)
    ass_path = "output/captions.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header)
        f.write("\n".join(ass_events))
        f.write("\n")

    print(f"Generated Kinetic ASS captions saved to {ass_path}")
    return ass_path
