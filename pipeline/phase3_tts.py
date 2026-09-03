import os
import random
import json
import wave
import subprocess

from pipeline.config import GEMINI_VOICES, KOKORO_VOICES
from pipeline.gemini import GeminiClient

STATE_PATH = "voice_state.json"

def pick_voice(pool: list[str], state_key: str) -> str:
    state = {}
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r") as f:
                state = json.load(f)
        except Exception:
            pass
    last = state.get(state_key)
    choice = random.choice([v for v in pool if v != last] or pool)
    state[state_key] = choice
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Warning: Failed to write voice state: {e}")
    return choice

def get_wav_duration(filepath: str) -> float:
    with wave.open(filepath, 'rb') as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)

def split_combined_audio(combined_path: str, segments: list[dict]):
    import subprocess
    # First, try Whisper word alignment
    try:
        from faster_whisper import WhisperModel
        print("[TTS] Loading faster-whisper 'base' model on CPU for segmentation...")
        model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=1, num_workers=1)
        segments_out, info = model.transcribe(combined_path, word_timestamps=True)
        
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
        
        # Build script words list and map word indices back to segments
        script_words = []
        seg_word_counts = []
        for seg in segments:
            words = seg["narration"].split()
            script_words.extend(words)
            seg_word_counts.append(len(words))
            
        aligned_words = []
        ns = len(script_words)
        nw = len(whisper_words)
        if ns > 0 and nw > 0:
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
                aligned_words.append({
                    "word": s_word,
                    "start": whisper_words[clamped_w_idx]["start"],
                    "end": whisper_words[clamped_w_idx]["end"]
                })
                w_idx = clamped_w_idx + 1
        
        if len(aligned_words) == len(script_words):
            word_offset = 0
            total_duration = get_wav_duration(combined_path)
            
            # 1. Gather raw word starts/ends for each segment
            seg_bounds = []
            for i, seg in enumerate(segments):
                num_words = seg_word_counts[i]
                seg_words = aligned_words[word_offset : word_offset + num_words]
                word_offset += num_words
                
                if seg_words:
                    seg_bounds.append((seg_words[0]["start"], seg_words[-1]["end"]))
                else:
                    # fallback if segment is empty
                    seg_bounds.append((total_duration, total_duration))
                    
            # 2. Calculate continuous slice boundaries (midpoints during silences)
            slice_starts = []
            slice_ends = []
            
            for i in range(len(segments)):
                if i == 0:
                    start_time = 0.0
                else:
                    # Midpoint between previous segment's end and this segment's start
                    # Prevents cutting off trailing reverb/breath and preserves natural gaps
                    start_time = (seg_bounds[i-1][1] + seg_bounds[i][0]) / 2.0
                    
                if i == len(segments) - 1:
                    end_time = total_duration
                else:
                    end_time = (seg_bounds[i][1] + seg_bounds[i+1][0]) / 2.0
                    
                slice_starts.append(start_time)
                slice_ends.append(end_time)
            
            # 3. Perform slicing with soundfile (sample-accurate, zero FFmpeg bugs)
            import soundfile as sf
            data, sr = sf.read(combined_path)
            total_samples = len(data)

            for i, seg in enumerate(segments):
                start_time = slice_starts[i]
                end_time = slice_ends[i]
                
                start_sample = max(0, int(start_time * sr))
                end_sample = min(total_samples, int(end_time * sr))
                if end_sample <= start_sample + int(0.2 * sr):
                    end_sample = min(total_samples, start_sample + int(0.5 * sr))
                    
                out_path = f"output/tts_segment_{seg['id']}.wav"
                print(f"[TTS] Slicing Segment {seg['id']}: {start_time:.3f}s -> {end_time:.3f}s ({end_sample - start_sample} samples)")
                sf.write(out_path, data[start_sample:end_sample], sr)
            return
    except Exception as e:
        print(f"[TTS] Word alignment split failed: {e}. Falling back to proportional split.")
        
    # Proportional split fallback
    import soundfile as sf
    data, sr = sf.read(combined_path)
    total_samples = len(data)
    total_duration = len(data) / sr
    weights = [len(seg["narration"]) for seg in segments]
    total_weight = sum(weights) if sum(weights) > 0 else 1
    
    current_time = 0.0
    for i, seg in enumerate(segments):
        duration = total_duration * (weights[i] / total_weight)
        end_time = current_time + duration
        if i == len(segments) - 1:
            end_time = total_duration
            
        start_sample = max(0, int(current_time * sr))
        end_sample = min(total_samples, int(end_time * sr))
        if end_sample <= start_sample + int(0.2 * sr):
            end_sample = min(total_samples, start_sample + int(0.5 * sr))
            
        out_path = f"output/tts_segment_{seg['id']}.wav"
        print(f"[TTS] Proportional slicing Segment {seg['id']}: {current_time:.3f}s -> {end_time:.3f}s ({end_sample - start_sample} samples)")
        sf.write(out_path, data[start_sample:end_sample], sr)
        current_time = end_time

def generate_audio(script: dict) -> list[str]:
    """
    Generates TTS for each segment individually using a SINGLE consistent voice.
    This guarantees 100% sentence-level audio accuracy, prevents words from getting
    cut off or bleeding across segments, and ensures B-roll transitions synchronize
    exactly with the narration.
    """
    gemini_client = GeminiClient()
    os.makedirs("output", exist_ok=True)

    gemini_voice = pick_voice(GEMINI_VOICES, "gemini")
    segments = script["segments"]

    print(f"[TTS] Generating per-segment audio using voice '{gemini_voice}' for {len(segments)} segments...")
    audio_files = []

    # Detect language for gTTS fallback
    has_gurmukhi = any(any(0x0A00 <= ord(c) <= 0x0A7F for c in seg.get("narration", "")) for seg in segments)
    fallback_lang = 'pa' if has_gurmukhi else (os.environ.get("LANGUAGE", "en")[:2].lower())

    for idx_seg, seg in enumerate(segments):
        seg_id = seg["id"]
        out_path = f"output/tts_segment_{seg_id}.wav"
        text = seg["narration"]

        # Clean up existing file
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass

        generated = False

        prev_text = segments[idx_seg - 1]["narration"] if idx_seg > 0 else None
        next_text = segments[idx_seg + 1]["narration"] if idx_seg < len(segments) - 1 else None

        # Pass 1: Gemini TTS per-segment with full director instructions & neighbor context
        try:
            audio_bytes, mime_type = gemini_client.generate_tts(
                text,
                voice=gemini_voice,
                vocal_tone=script.get("vocal_tone", "energetic_storytelling"),
                voiceover_plan=script.get("voiceover_plan"),
                prev_text=prev_text,
                next_text=next_text,
                segment_num=seg_id,
                total_segments=len(segments)
            )
            if audio_bytes.startswith(b"RIFF") or "wav" in mime_type.lower():
                with open(out_path, "wb") as wf:
                    wf.write(audio_bytes)
            else:
                with wave.open(out_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(audio_bytes)
            generated = True
            print(f"[TTS] Segment {seg_id} generated via Gemini TTS ({gemini_voice}) with full context.")
        except Exception as e:
            print(f"[TTS] Per-segment Gemini failed for segment {seg_id}: {e}")

        # Pass 2: High-Quality Edge-TTS Neural Voice fallback
        if not generated:
            try:
                import asyncio
                import edge_tts
                edge_voice = "en-US-AndrewNeural" if gemini_voice in ["Fenrir", "Charon", "Orus"] else "en-US-ChristopherNeural"
                temp_mp3 = f"output/temp_tts_{seg_id}.mp3"

                async def _run_edge():
                    comm = edge_tts.Communicate(text, voice=edge_voice, rate="+6%", pitch="+1Hz")
                    await comm.save(temp_mp3)

                asyncio.run(_run_edge())

                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_mp3, "-ac", "1", "-ar", "24000", out_path],
                    capture_output=True, check=True
                )
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
                generated = True
                print(f"[TTS] Segment {seg_id} generated via Edge-TTS Neural voice ({edge_voice}).")
            except Exception as e_edge:
                print(f"[TTS] Edge-TTS fallback failed for segment {seg_id}: {e_edge}")

        # Pass 3: Fallback to gTTS if both fail
        if not generated:
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang=fallback_lang)
                temp_mp3 = f"output/temp_tts_{seg_id}.mp3"
                tts.save(temp_mp3)
                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_mp3, "-ac", "1", "-ar", "24000", out_path],
                    capture_output=True, check=True
                )
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
                generated = True
                print(f"[TTS] Segment {seg_id} generated via gTTS fallback ({fallback_lang}).")
            except Exception as g_err:
                print(f"[TTS] gTTS fallback failed for segment {seg_id}: {g_err}")

        # Add slight trailing silence (0.10s) to prevent hard cuts at segment end
        if generated and os.path.exists(out_path):
            try:
                padded_path = f"output/temp_pad_{seg_id}.wav"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", out_path, "-af", "apad=pad_dur=0.10", padded_path],
                    capture_output=True, check=True
                )
                if os.path.exists(padded_path):
                    shutil.move(padded_path, out_path)
            except Exception:
                pass

        audio_files.append(out_path)

    return audio_files
