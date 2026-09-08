"""
sfx.py — Dynamic sound effects generator for yt-auto pipeline.
Generates whoosh (clip transitions) and snap (text pop-in) sounds.
Uses Freesound API with synthetic fallbacks.

All audio at 44100 Hz, mono, int16.
"""
import os
import random
import wave
import numpy as np


def _synth_whoosh(sample_rate: int = 44100, duration: float = 0.38) -> np.ndarray:
    """
    Synthetic whoosh: logarithmic frequency sweep (4kHz→200Hz) + noise, shaped envelope.
    Sounds like a quick air rush — ideal for clip-to-clip transitions.
    """
    t       = np.linspace(0, duration, int(sample_rate * duration))
    # Frequency sweep from 4000 Hz down to 200 Hz (logarithmic)
    freq    = np.exp(np.linspace(np.log(4000), np.log(200), len(t)))
    phase   = np.cumsum(2 * np.pi * freq / sample_rate)
    sweep   = np.sin(phase)
    # White noise layer
    noise   = np.random.randn(len(t)) * 0.35
    # Combine sweep + noise
    signal  = sweep * 0.65 + noise * 0.35
    # Envelope: very fast attack (15ms), slow exponential decay
    attack  = 1 - np.exp(-t * 200)
    decay   = np.exp(-t * 9)
    env     = attack * decay
    sfx     = signal * env
    sfx    /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.65).astype(np.int16)


def _synth_digital_whoosh(sample_rate: int = 44100, duration: float = 0.45) -> np.ndarray:
    """Synthetic sci-fi digital whoosh: sine sweep + vibrato + noise."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    freq = 1800 - 1400 * (t / duration) + 200 * np.sin(2 * np.pi * 30 * t)
    phase = np.cumsum(2 * np.pi * freq / sample_rate)
    sig = np.sin(phase) * 0.75 + np.random.randn(len(t)) * 0.1
    env = np.sin(np.pi * (t / duration)) ** 1.8
    sfx = sig * env
    sfx /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.55).astype(np.int16)


def _synth_snap(sample_rate: int = 44100) -> np.ndarray:
    """
    Synthetic snap/click: short sharp transient.
    Sounds like a camera shutter or finger snap.
    Use when a key image or text pops into frame.
    """
    duration = 0.055
    t        = np.linspace(0, duration, int(sample_rate * duration))
    noise    = np.random.randn(len(t))
    # Very fast exponential decay (0 → silence in ~50ms)
    env      = np.exp(-t * 130)
    sfx      = noise * env
    sfx     /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.45).astype(np.int16)


def _synth_impact(sample_rate: int = 44100, duration: float = 1.0) -> np.ndarray:
    """Standard synthetic boom fallback."""
    return _synth_niche_impact("general", sample_rate=sample_rate, duration=duration)


def _synth_nature_whoosh(sample_rate: int = 44100, duration: float = 0.42) -> np.ndarray:
    """Organic wind rush / rustle whoosh."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    noise = np.random.randn(len(t))
    env = np.sin(np.pi * (t / duration)) ** 2.2
    kernel = np.ones(15) / 15
    smooth_noise = np.convolve(noise, kernel, mode='same')
    sfx = smooth_noise * env
    sfx /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.60).astype(np.int16)


def _synth_blade_whoosh(sample_rate: int = 44100, duration: float = 0.35) -> np.ndarray:
    """Historical warfare sword slice / arrow whoosh."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    freq = np.exp(np.linspace(np.log(2800), np.log(140), len(t)))
    sweep = np.sin(np.cumsum(2 * np.pi * freq / sample_rate))
    noise = np.random.randn(len(t)) * 0.25
    env = (1 - np.exp(-t * 180)) * np.exp(-t * 11)
    sfx = (sweep * 0.7 + noise * 0.3) * env
    sfx /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.65).astype(np.int16)


def _synth_reverse_whoosh(sample_rate: int = 44100, duration: float = 0.48) -> np.ndarray:
    """Mystery eerie reverse-swell whoosh."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    freq = 150 + 1200 * (t / duration) ** 2
    sweep = np.sin(np.cumsum(2 * np.pi * freq / sample_rate))
    env = (t / duration) ** 2.5 * np.exp(-(1 - t / duration) * 4)
    sfx = (sweep + np.random.randn(len(t)) * 0.2) * env
    sfx /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.58).astype(np.int16)


def _synth_hydraulic_whoosh(sample_rate: int = 44100, duration: float = 0.40) -> np.ndarray:
    """Engineering hydraulic piston hiss / pneumatic release whoosh."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    noise = np.random.randn(len(t))
    env = np.exp(-t * 7.5) * (1 - np.exp(-t * 300))
    sub = np.sin(2 * np.pi * 90 * t) * np.exp(-t * 15) * 0.4
    sfx = (noise * 0.7 + sub) * env
    sfx /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.65).astype(np.int16)


def _synth_niche_impact(foley_type: str, sample_rate: int = 44100, duration: float = 1.0) -> np.ndarray:
    """Synthetic cinematic impact tailored to the channel's niche and soundscape."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    if foley_type == "digital_tech":
        # Quantum singularity drop: 240Hz down to 28Hz with data transient
        freq = 28 + 210 * np.exp(-t * 14)
        sig = np.sin(np.cumsum(2 * np.pi * freq / sample_rate)) * 0.8
        sig += np.random.randn(len(t)) * np.exp(-t * 50) * 0.2
        env = np.exp(-t * 3.2)
    elif foley_type == "organic_nature":
        # Deep seismic earth tremor: 60Hz down to 22Hz, soft organic attack
        freq = 22 + 40 * np.exp(-t * 6)
        sig = np.sin(np.cumsum(2 * np.pi * freq / sample_rate))
        env = (1 - np.exp(-t * 60)) * np.exp(-t * 2.8)
    elif foley_type == "historical_warfare":
        # Anvil / warhammer heavy bronze impact
        freq = 35 + 140 * np.exp(-t * 16)
        sub = np.sin(np.cumsum(2 * np.pi * freq / sample_rate))
        ring = np.sin(2 * np.pi * 540 * t) * np.exp(-t * 9) * 0.4
        sig = sub * 0.7 + ring + np.random.randn(len(t)) * np.exp(-t * 60) * 0.3
        env = np.exp(-t * 3.0)
    elif foley_type == "mystery_eerie":
        # Low eerie sub-thud with detuned interval
        f1 = 30 + 90 * np.exp(-t * 8)
        f2 = 45 + 135 * np.exp(-t * 8)
        sig = (np.sin(np.cumsum(2 * np.pi * f1 / sample_rate)) + 0.6 * np.sin(np.cumsum(2 * np.pi * f2 / sample_rate))) * 0.7
        sig += np.random.randn(len(t)) * np.exp(-t * 30) * 0.2
        env = np.exp(-t * 2.5)
    elif foley_type == "industrial_machinery":
        # Heavy pile driver mechanical crash
        freq = 32 + 180 * np.exp(-t * 18)
        sig = np.sin(np.cumsum(2 * np.pi * freq / sample_rate)) * 0.75
        metal_click = np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 80) * 0.5
        sig += (np.random.randn(len(t)) * 0.4 + metal_click) * np.exp(-t * 40)
        env = np.exp(-t * 3.8)
    else:
        freq = 30 + 120 * np.exp(-t * 12)
        sig = np.sin(np.cumsum(2 * np.pi * freq / sample_rate)) * 0.75 + np.random.randn(len(t)) * np.exp(-t * 45) * 0.25
        env = np.exp(-t * 3.5)
    sfx = sig * env
    sfx /= np.max(np.abs(sfx)) + 1e-9
    return (sfx * 32767 * 0.85).astype(np.int16)


def _fetch_freesound_sfx(query: str, max_duration: float = 2.0) -> str | None:
    """
    Search Freesound for a short transition/whoosh sound and download/cache it.
    """
    import requests
    try:
        from pipeline.config import FREESOUND_API_KEY
    except ImportError:
        return None
    if not FREESOUND_API_KEY:
        return None

    search_url = "https://freesound.org/apiv2/search/text/"
    params = {
        "query": query,
        "filter": f'duration:[0.1 TO {max_duration}] license:"Creative Commons 0"',
        "fields": "id,name,duration,previews",
        "page_size": 8,
        "token": FREESOUND_API_KEY,
    }
    try:
        resp = requests.get(search_url, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as exc:
        print(f"[SFX] Freesound search failed: {exc}")
        return None

    if not results:
        return None

    pick = random.choice(results)
    sound_id = pick.get("id")
    preview_url = pick.get("previews", {}).get("preview-hq-mp3")
    if not preview_url:
        return None

    cache_dir = "cache_sfx"
    cache_path = os.path.join(cache_dir, f"sfx_{sound_id}.wav")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        return cache_path

    print(f"[SFX] Downloading Freesound SFX #{sound_id}: {pick['name']}")
    import tempfile
    import shutil
    import subprocess
    tmpdir = tempfile.mkdtemp(prefix="freesound_sfx_")
    tmp_mp3 = os.path.join(tmpdir, "temp.mp3")
    tmp_wav = os.path.join(tmpdir, "temp.wav")
    try:
        dl = requests.get(preview_url, timeout=15)
        dl.raise_for_status()
        with open(tmp_mp3, "wb") as f:
            f.write(dl.content)

        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "44100", "-ac", "1", tmp_wav],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        )
        os.makedirs(cache_dir, exist_ok=True)
        shutil.copy(tmp_wav, cache_path)
        return cache_path
    except Exception as exc:
        print(f"[SFX] Freesound SFX download/convert failed: {exc}")
        return None


def _read_wav_file(filepath: str) -> np.ndarray:
    with wave.open(filepath, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        data = wf.readframes(n_frames)
        
        if sampwidth == 2:
            sig = np.frombuffer(data, dtype=np.int16)
        elif sampwidth == 1:
            sig = (np.frombuffer(data, dtype=np.uint8).astype(np.int16) - 128) * 256
        else:
            raise ValueError("Unsupported sample width")
            
        if n_channels > 1:
            sig = sig.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
            
        return sig



def _fetch_cached_sfx(category: str) -> str | None:
    # 1. Check local repository cache_sfx first
    cache_dir = "cache_sfx"
    category_files = {
        "dramatic_boom": ["sfx_19284.wav", "sfx_19288.wav", "sfx_461943.wav"],
        "pop_ding": ["sfx_644944.wav", "sfx_644945.wav", "sfx_644946.wav", "sfx_644947.wav"],
        "record_scratch": ["sfx_633719.wav", "sfx_824189.wav"],
        "success_chime": ["sfx_706089.wav", "sfx_741580.wav"],
        "transition_whoosh": ["sfx_59537.wav", "sfx_575239.wav", "sfx_221361.wav", "sfx_584176.wav"]
    }
    candidates = category_files.get(category, [])
    for c_file in candidates:
        p = os.path.join(cache_dir, c_file)
        if os.path.exists(p) and os.path.getsize(p) > 500:
            return p

    # 2. Remote Freesound fallback
    queries = {
        "pop_ding": ["cartoon pop sfx", "ui button pop click", "bubble pop sound"],
        "dramatic_boom": ["vine boom", "cinematic shock boom hit", "sub bass drop"],
        "success_chime": ["ding correct", "success chime bell", "retro game ding"],
        "record_scratch": ["record scratch stop", "dj scratch stop", "glitch transition error"]
    }
    
    q_list = queries.get(category, [])
    for q in q_list:
        path = _fetch_freesound_sfx(q, max_duration=1.5)
        if path:
            return path
    return None


def create_sfx_track(
    clip_boundary_times: list[float],
    total_duration: float,
    sample_rate: int = 44100,
    whoosh_volume: float = 0.30,
    topic: str = "",
) -> str:
    """
    Build a single WAV track that contains:
    - A dramatic boom/hit at t=0
    - A transition whoosh at each clip boundary
    - A pop/ding sound during Segment 1 fact reveal
    - A record scratch/glitch during Segment 2 plot twist
    - A success chime at the start of the final CTA segment
    """
    os.makedirs("output", exist_ok=True)

    total_samples = int(total_duration * sample_rate)
    track         = np.zeros(total_samples, dtype=np.float64)

    from pipeline.config import get_channel_profile
    channel_niche = os.environ.get("CHANNEL_NICHE", "science").lower()
    profile = get_channel_profile(channel_niche)
    foley_type = profile.get("foley_type", "digital_tech")

    # 1. Load sound effects
    boom_sig = None
    boom_path = _fetch_cached_sfx("dramatic_boom")
    if boom_path:
        try:
            boom_sig = _read_wav_file(boom_path)
        except Exception:
            pass
    if boom_sig is None:
        boom_sig = _synth_niche_impact(foley_type, sample_rate)

    pop_sig = None
    pop_path = _fetch_cached_sfx("pop_ding")
    if pop_path:
        try:
            pop_sig = _read_wav_file(pop_path)
        except Exception:
            pass
    if pop_sig is None:
        pop_sig = _synth_snap(sample_rate)

    scratch_sig = None
    scratch_path = _fetch_cached_sfx("record_scratch")
    if scratch_path:
        try:
            scratch_sig = _read_wav_file(scratch_path)
        except Exception:
            pass
    if scratch_sig is None:
        scratch_sig = _synth_digital_whoosh(sample_rate, duration=0.3)

    chime_sig = None
    chime_path = _fetch_cached_sfx("success_chime")
    if chime_path:
        try:
            chime_sig = _read_wav_file(chime_path)
        except Exception:
            pass
    if chime_sig is None:
        chime_sig = _synth_snap(sample_rate) # fallback to snap

    # Place opening impact/boom at t=0
    end_imp = min(total_samples, len(boom_sig))
    if end_imp > 0:
        track[0:end_imp] += (boom_sig[:end_imp].astype(np.float64) / 32767) * 0.70

    # Calculate segment start/end times
    segment_times = [0.0] + clip_boundary_times + [total_duration]

    def _niche_whoosh():
        if foley_type == "digital_tech":
            return _synth_digital_whoosh(sample_rate)
        elif foley_type == "organic_nature":
            return _synth_nature_whoosh(sample_rate)
        elif foley_type == "historical_warfare":
            return _synth_blade_whoosh(sample_rate)
        elif foley_type == "mystery_eerie":
            return _synth_reverse_whoosh(sample_rate)
        elif foley_type == "industrial_machinery":
            return _synth_hydraulic_whoosh(sample_rate)
        return _synth_whoosh(sample_rate)

    # Whooshes at clip boundaries
    whoosh_pool = []
    cache_dir = "cache_sfx"
    whoosh_filenames = ["sfx_59537.wav", "sfx_575239.wav", "sfx_221361.wav", "sfx_584176.wav", "sfx_392697.wav", "sfx_423930.wav"]
    for wf in whoosh_filenames:
        wp = os.path.join(cache_dir, wf)
        if os.path.exists(wp):
            try:
                whoosh_pool.append(_read_wav_file(wp))
            except Exception:
                pass
    if not whoosh_pool and topic:
        topic_words = [w for w in topic.lower().split() if len(w) > 4]
        queries = ["whoosh", "swoosh", "transition swoosh", "cinematic transition", "digital transition"]
        if topic_words:
            queries = [f"{topic_words[0]} whoosh"] + queries
        for q in queries[:3]:
            path = _fetch_freesound_sfx(q, max_duration=1.5)
            if path:
                try:
                    whoosh_pool.append(_read_wav_file(path))
                except Exception:
                    pass

    for t_sec in clip_boundary_times:
        if whoosh_pool:
            w_sig = random.choice(whoosh_pool)
        else:
            w_sig = _niche_whoosh()

        start = max(0, int((t_sec - 0.12) * sample_rate))
        end   = min(total_samples, start + len(w_sig))
        length = end - start
        if length > 0:
            track[start:end] += (w_sig[:length].astype(np.float64) / 32767) * whoosh_volume

    # Place context-appropriate meme/trendy SFX:
    # 1. Pop/Ding during Segment 1 mid-point
    if len(segment_times) >= 3:
        seg1_mid = (segment_times[1] + segment_times[2]) / 2.0
        start = max(0, int(seg1_mid * sample_rate))
        end = min(total_samples, start + len(pop_sig))
        if end - start > 0:
            track[start:end] += (pop_sig[:end-start].astype(np.float64) / 32767) * 0.35

    # 2. Record scratch / glitch at Segment 2 start
    if len(segment_times) >= 4:
        seg2_start = segment_times[2]
        start = max(0, int(seg2_start * sample_rate))
        end = min(total_samples, start + len(scratch_sig))
        if end - start > 0:
            track[start:end] += (scratch_sig[:end-start].astype(np.float64) / 32767) * 0.30

    # 3. Success chime at start of final CTA segment
    if len(segment_times) >= 3:
        cta_start = segment_times[-2]
        start = max(0, int(cta_start * sample_rate))
        end = min(total_samples, start + len(chime_sig))
        if end - start > 0:
            track[start:end] += (chime_sig[:end-start].astype(np.float64) / 32767) * 0.40

    # Clip to int16
    track_int16 = np.clip(track * 32767, -32768, 32767).astype(np.int16)
    out_path    = "output/sfx_track.wav"
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(track_int16.tobytes())
    print(f"[SFX] Custom SFX track created with booms, pops, scratches, and chimes.")
    return out_path

