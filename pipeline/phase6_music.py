"""
phase6_music.py — Procedural ambient background music generator.
Generates calm chord-pad loops with a soft shaker pulse using pure numpy.
No torch, no transformers, no model download, no OOM risk. Runs in <2s.

If a FREESOUND_API_KEY is set, tries Freesound CC0 ambient tracks first,
then falls back to the procedural generator on any failure.
"""
import json
import os
import random
import shutil
import subprocess
import tempfile
import numpy as np
import wave

SAMPLE_RATE = 44100
_NOTE_FREQS = {  # octave-4 reference frequencies
    "C": 261.63, "C#": 277.18, "D": 293.66, "D#": 311.13, "E": 329.63,
    "F": 349.23, "F#": 369.99, "G": 392.00, "G#": 415.30, "A": 440.00,
    "A#": 466.16, "B": 493.88,
}
# Calm/ambient 4-chord loops: (root, quality)
_PROGRESSIONS = [
    [("C", "maj"), ("A", "min"), ("F", "maj"), ("G", "maj")],
    [("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")],
    [("D", "min"), ("A#", "maj"), ("F", "maj"), ("C", "maj")],
    [("E", "min"), ("C", "maj"), ("G", "maj"), ("D", "maj")],
]


def _clean_music_query(topic: str) -> str:
    if ":" in topic:
        topic = topic.split(":")[0]
    
    clean = topic.strip().lower()
    intros = [
        "what most people don't know about",
        "what most people don't know about the",
        "the hidden truth about",
        "the hidden truth about the",
        "the secret of",
        "the secret of the",
        "the mystery of",
        "the mystery of the",
        "what you didn't know about",
        "what you didn't know about the",
        "scientists found something inside",
        "scientists found something inside the",
    ]
    for intro in intros:
        if clean.startswith(intro):
            clean = clean[len(intro):].strip()
            break
    return clean


def _adsr(n, attack, release):
    env = np.ones(n)
    a, r = min(attack, n // 2), min(release, n // 2)
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] = np.linspace(1, 0, r)
    return env


def _chord(root, quality, duration, base_octave=3):
    intervals = [0, 4, 7] if quality == "maj" else [0, 3, 7]
    root_freq = _NOTE_FREQS[root] / (2 ** (4 - base_octave))
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0, duration, n, endpoint=False)
    wave = sum(np.sin(2 * np.pi * root_freq * (2 ** (iv / 12)) * t) for iv in intervals)
    wave += 0.6 * np.sin(2 * np.pi * (root_freq / 2) * t)          # sub-bass, -1 octave
    return wave * _adsr(n, int(0.35 * SAMPLE_RATE), int(0.6 * SAMPLE_RATE))


def _shaker(n_samples, beat_samples):
    track = np.zeros(n_samples)
    tt = np.linspace(0, 0.05, int(0.05 * SAMPLE_RATE))
    hit = np.random.randn(len(tt)) * np.exp(-tt * 90) * 0.08
    for start in range(0, n_samples - len(hit), beat_samples):
        track[start:start + len(hit)] += hit
    return track


def _ticking_clock(n_samples, tick_interval_samples):
    track = np.zeros(n_samples)
    t_tick = np.linspace(0, 0.015, int(0.015 * SAMPLE_RATE))
    # A fast-decay sine hit (1500Hz) combined with short noise burst for a crisp clock click
    tick_sound = np.sin(2 * np.pi * 1500 * t_tick) * np.exp(-t_tick * 400) * 0.08
    tick_sound += np.random.randn(len(t_tick)) * np.exp(-t_tick * 500) * 0.02
    for start in range(0, n_samples - len(tick_sound), tick_interval_samples):
        track[start:start + len(tick_sound)] += tick_sound
    return track


def _fetch_freesound_music(topic: str, duration_seconds: int) -> str | None:
    """Try to download a CC0 ambient track from Freesound. Returns wav path or None."""
    try:
        import requests
        from pipeline.config import FREESOUND_API_KEY
    except ImportError:
        return None
    if not FREESOUND_API_KEY:
        return None

    search_url = "https://freesound.org/apiv2/search/text/"
    
    is_history, is_engineering, is_natural = False, False, False
    channel_env = os.environ.get("CHANNEL_NICHE", "").lower()
    if channel_env == "nature":
        is_natural = True
    elif channel_env == "history":
        is_history = True
    elif channel_env == "engineering":
        is_engineering = True
    try:
        from pipeline.config import HISTORY_SUBCLUSTERS
        is_history = True
    except ImportError:
        pass
    try:
        from pipeline.config import ENGINEERING_SUBCLUSTERS
        is_engineering = True
    except ImportError:
        pass
    try:
        from pipeline.config import NATURAL_WORLD_SUBCLUSTERS
        is_natural = True
    except ImportError:
        pass

    clean_topic = _clean_music_query(topic)

    if "wedding" in topic.lower() or "marriage" in topic.lower() or "romantic" in topic.lower():
        queries = [f"{clean_topic} ambient", "romantic wedding ambient", "indian wedding instrumental"]
    elif is_history:
        queries = [f"{clean_topic} orchestral tension", "cinematic historical music", "medieval tension ambient", "ancient history ambient"]
    elif is_engineering:
        queries = [f"{clean_topic} industrial tech", "machinery industrial ambient", "cinematic suspense synth", "ambient tech synth"]
    elif is_natural:
        queries = [f"{clean_topic} nature ambient", "wildlife cinematic music", "calm flute ambient", "earth atmospheric loop"]
    else:
        queries = [f"{clean_topic} space cinematic", "cinematic suspense synth", "sci-fi tension loop", "ambient space synth"]



    for query in queries:
        print(f"[Music] Searching Freesound for '{query}' ...")
        params = {
            "query": query,
            "filter": f'duration:[{duration_seconds} TO {duration_seconds * 4}] license:"Creative Commons 0"',
            "fields": "id,name,duration,previews",
            "page_size": 5,
            "token": FREESOUND_API_KEY,
        }
        try:
            resp = requests.get(search_url, params=params, timeout=30)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as exc:
            print(f"[Music] Freesound search failed: {exc}")
            continue

        if not results:
            print(f"[Music] No Freesound results for '{query}', trying next query...")
            continue

        pick = random.choice(results)
        sound_id = pick.get("id")
        preview_url = pick.get("previews", {}).get("preview-hq-mp3")
        if not preview_url:
            print("[Music] Selected result has no HQ preview, skipping.")
            continue

        cache_dir = "cache_music"
        cache_path = os.path.join(cache_dir, f"freesound_{sound_id}.wav")
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
            print(f"[Music] Found cached Freesound track #{sound_id} → {cache_path}")
            return cache_path

        print(f"[Music] Downloading Freesound #{sound_id}: {pick['name']} ({pick['duration']:.1f}s)")
        tmpdir = tempfile.mkdtemp(prefix="freesound_")
        tmp_mp3 = os.path.join(tmpdir, "temp.mp3")
        tmp_wav = os.path.join(tmpdir, "temp.wav")
        try:
            dl = requests.get(preview_url, timeout=30)
            dl.raise_for_status()
            with open(tmp_mp3, "wb") as f:
                f.write(dl.content)

            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "44100", "-ac", "1", tmp_wav],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
            )
            print("[Music] Freesound track converted to wav successfully.")
            
            # Save to cache
            os.makedirs(cache_dir, exist_ok=True)
            shutil.copy(tmp_wav, cache_path)
            print(f"[Music] Cached Freesound track to {cache_path}")
            
            return tmp_wav
        except Exception as exc:
            print(f"[Music] Freesound download/convert failed: {exc}")
            continue

    return None


def _archive_audio(topic: str) -> str | None:
    try:
        import requests
        clean_topic = _clean_music_query(topic)
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f'({clean_topic} ambient) AND mediatype:audio AND licenseurl:"https://creativecommons.org/publicdomain/zero/1.0/"',
                "fl[]": "identifier",
                "rows": 5,
                "output": "json",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        if not docs:
            return None
        pick = random.choice(docs[:3])
        identifier = pick["identifier"]
        # Fetch the actual file list for this item
        meta = requests.get(
            f"https://archive.org/metadata/{identifier}",
            timeout=15
        ).json()
        files = [f for f in meta.get("files", [])
                 if f.get("format", "").lower() in ("mp3", "ogg vorbis", "flac")]
        if not files:
            return None
        f = files[0]
        return f"https://archive.org/download/{identifier}/{f['name']}"
    except Exception as e:
        print(f"[Music] Archive audio failed: {e}")
        return None


NICHE_TRACK_METADATA = {
    "science": {
        "crypto.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Crypto.mp3", ["quantum", "computing", "ai", "paradox", "simulation", "algorithm", "silicon", "time", "ground floor", "black hole", "relativity", "micro-robot", "circuit"]),
        "the_complex.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Complex.mp3", ["cyber", "hacking", "digital", "neural", "electric", "futuristic", "particle", "laser", "physics", "spokes"]),
        "future_gladiator.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Future%20Gladiator.mp3", ["robot", "combat", "kinetic", "energy", "fusion", "breakthrough", "materials", "engine"]),
        "static_motion.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Static%20Motion.mp3", ["cosmic", "galaxy", "deep space", "nebula", "radiation", "universe", "astronomy", "saturn", "rings"]),
        "overriding_concern.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Overriding%20Concern.mp3", ["experiment", "nuclear", "chemistry", "mutation", "danger", "hazard", "reaction", "laboratory"]),
        "echoes_of_time.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Echoes%20of%20Time.mp3", ["spacetime", "ancient stars", "telescope", "gravitational", "light", "dimension", "infinite"]),
    },
    "nature": {
        "dark_fog.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dark%20Fog.mp3", ["deep sea", "abyss", "bioluminescence", "squid", "shark", "anglerfish", "predator", "ocean", "trench"]),
        "thunder_dreams.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Thunder%20Dreams.mp3", ["apex", "colossal", "whale", "giant", "mammal", "elephant", "lethal", "water"]),
        "deep_noise.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Deep%20Noise.mp3", ["subterranean", "cave", "fungi", "strange", "unseen", "creature", "darkness", "blind"]),
        "long_note_two.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Long%20Note%20Two.mp3", ["immortal", "tardigrade", "regeneration", "frozen", "ancient", "microscopic", "bacteria", "fossil", "coelacanth"]),
        "spacial_harvest.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Spacial%20Harvest.mp3", ["parasite", "mimicry", "adaptation", "bizarre", "evolution", "strike", "mantis shrimp", "plasma"]),
        "shamanistic.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Shamanistic.mp3", ["jungle", "forest", "survival", "instinct", "hunt", "primal", "predator", "wild"]),
    },
    "history": {
        "five_armies.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Five%20Armies.mp3", ["battle", "legion", "siege", "empire", "cavalry", "army", "ancient", "rome", "spartan"]),
        "clash_defiant.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clash%20Defiant.mp3", ["guerrilla", "traps", "declassified", "military", "deception", "ghost army", "wwii", "inflatable"]),
        "hitman.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hitman.mp3", ["assassin", "spy", "ninja", "secret", "treaty", "poison", "shadow", "ambush", "fog"]),
        "prelude_and_action.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Prelude%20and%20Action.mp3", ["tactics", "maneuver", "artillery", "command", "warrior", "weapon", "rubber", "chemistry"]),
        "dangerous.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dangerous.mp3", ["invasion", "blockade", "conquest", "doom", "ruthless", "warlord", "catastrophe"]),
        "volatile_reaction.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3", ["gunpowder", "blitzkrieg", "revolution", "rebellion", "castle", "explosive", "charge"]),
    },
    "mystery": {
        "unseen_horrors.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Unseen%20Horrors.mp3", ["cold case", "vanished", "anomaly", "sighting", "creature", "cryptid", "forest", "cave", "patagonia", "baghdad battery"]),
        "metaphysik.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Metaphysik.mp3", ["ancient ruins", "radio", "signal", "cosmic", "radio burst", "bursts", "void", "space", "sun"]),
        "awkward_meeting.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Awkward%20Meeting.mp3", ["bunker", "classified", "ufo", "government", "files", "project", "conspiracy"]),
        "symmetry.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Symmetry.mp3", ["geometric", "richat", "structure", "sahara", "orbit", "megalith", "circle", "formation"]),
        "anxiety.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Anxiety.mp3", ["enigma", "lost", "bermuda", "chilling", "disturbing", "unsolved", "paradox"]),
        "evening_fall_-_harp.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Evening%20Fall%20-%20Harp.mp3", ["civilization", "sunken", "crypt", "tomb", "pyramid", "haunting", "legend"]),
    },
    "engineering": {
        "mechanolith.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mechanolith.mp3", ["tunnel", "bridge", "excavator", "skyscraper", "structure", "akashi", "suspension", "earthquake"]),
        "industrial_cinematic.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Industrial%20Cinematic.mp3", ["subsea", "oil rig", "space elevator", "mega", "breakthrough", "concrete", "ocean", "rock"]),
        "heavy_interlude.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heavy%20Interlude.mp3", ["crane", "cern", "particle", "collider", "reactor", "fusion", "quantum"]),
        "militaire_electronic.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Militaire%20Electronic.mp3", ["supersonic", "sr-71", "aircraft", "hypersonic", "submarine", "mach"]),
        "noise_attack.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Noise%20Attack.mp3", ["mach 10", "heat shield", "thruster", "rocket", "hyperloop", "speed", "self-repairing"]),
        "neolith.wav": ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/Neolith.mp3", ["dam", "three gorges", "panama", "colossal", "megastructure", "foundation", "living concrete"]),
    }
}


def generate_music(topic: str, duration_seconds: int = 35) -> str:
    out_path = "output/music.wav"
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        print("Background music already exists, skipping generation.")
        return out_path

    # ── Priority 1: High-Quality Studio Fleet Music Library in cache_music/ ──
    cache_dir = "cache_music"
    os.makedirs(cache_dir, exist_ok=True)
    niche = os.environ.get("CHANNEL_NICHE", "").lower()
    if not niche:
        # Detect from topic
        top_lower = topic.lower()
        if any(w in top_lower for w in ["space", "science", "quantum", "crystal", "chemistry", "relativity", "ai", "physics", "telescope"]):
            niche = "science"
        elif any(w in top_lower for w in ["mystery", "unsolved", "secret", "cryptid", "anomaly", "enigma", "disappeared", "vanish"]):
            niche = "mystery"
        elif any(w in top_lower for w in ["history", "war", "ancient", "battle", "siege", "empire", "soldier", "army"]):
            niche = "history"
        elif any(w in top_lower for w in ["animal", "ocean", "nature", "species", "abyss", "squid", "shark", "predator", "biology"]):
            niche = "nature"
        elif any(w in top_lower for w in ["mega", "engine", "build", "bridge", "tunnel", "dam", "machinery", "aircraft", "structure"]):
            niche = "engineering"
        else:
            niche = "science"

    niche_tracks = NICHE_TRACK_METADATA.get(niche, NICHE_TRACK_METADATA["science"])
    
    # Load recent history to prevent playing the exact same track twice in a row
    history_file = "music_history.json"
    recent_history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as hf:
                recent_history = json.load(hf)
        except Exception:
            recent_history = []

    # Score each track against topic keywords
    top_lower = topic.lower()
    scores = {}
    for track_file, (dl_url, kws) in niche_tracks.items():
        score = 0
        for kw in kws:
            if kw in top_lower:
                score += 3
        # Penalize recently used track
        if track_file in recent_history[-2:]:
            score -= 5
        scores[track_file] = score

    sorted_tracks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_track_name = sorted_tracks[0][0]
    best_url = niche_tracks[best_track_name][0]
    local_track_path = os.path.join(cache_dir, best_track_name)

    print(f"[Music] Topic match for '{niche}': selected '{best_track_name}' (Score: {sorted_tracks[0][1]})")

    # If track doesn't exist locally, auto-download from high-speed CDN and convert to WAV
    if not (os.path.exists(local_track_path) and os.path.getsize(local_track_path) > 100000):
        print(f"[Music] Track '{best_track_name}' not cached. Downloading from CDN: {best_url} ...")
        try:
            import urllib.request
            tmp_mp3 = f"/tmp/{best_track_name}.mp3"
            req = urllib.request.Request(best_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_mp3, "wb") as f:
                f.write(resp.read())
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "44100", "-ac", "1", local_track_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
            if os.path.exists(tmp_mp3): os.remove(tmp_mp3)
            print(f"[Music] Successfully downloaded and cached '{best_track_name}' ({os.path.getsize(local_track_path) // 1024} KB)")
        except Exception as dl_err:
            print(f"[Music] CDN download failed for '{best_track_name}': {dl_err}. Trying any existing local wav...")

    # If selected track exists, use it
    if os.path.exists(local_track_path) and os.path.getsize(local_track_path) > 100000:
        os.makedirs("output", exist_ok=True)
        shutil.copy(local_track_path, out_path)
        # Update history
        recent_history.append(best_track_name)
        try:
            with open(history_file, "w") as hf:
                json.dump(recent_history[-10:], hf)
        except Exception:
            pass
        print(f"[Music] Selected authentic studio production track ({niche}): {best_track_name} -> {out_path}")
        return out_path

    # Secondary fallback: any valid WAV in cache_dir
    local_wavs = [os.path.join(cache_dir, f) for f in os.listdir(cache_dir) if f.endswith(".wav") and os.path.getsize(os.path.join(cache_dir, f)) > 100000]
    if local_wavs:
        chosen = random.choice(local_wavs)
        print(f"[Music] Using local library fallback: {chosen}")
        os.makedirs("output", exist_ok=True)
        shutil.copy(chosen, out_path)
        return out_path

    # ── Priority 2: Freesound CC0 ambient track search ────────────────────────
    try:
        fs_wav = _fetch_freesound_music(topic, duration_seconds)
        if fs_wav and os.path.exists(fs_wav) and os.path.getsize(fs_wav) > 1000:
            os.makedirs("output", exist_ok=True)
            shutil.copy(fs_wav, out_path)
            print(f"[Music] Using Freesound CC0 track → {out_path}")
            return out_path
    except Exception as exc:
        print(f"[Music] Freesound attempt failed ({exc})")

    # ── Try Internet Archive Audio CC0 second ────────────────────────────────
    try:
        print(f"[Music] Searching Internet Archive audio for '{topic}'...")
        arch_url = _archive_audio(topic)
        if arch_url:
            print(f"[Music] Downloading Internet Archive audio: {arch_url}")
            import requests
            import tempfile
            dl = requests.get(arch_url, timeout=40)
            dl.raise_for_status()
            with tempfile.TemporaryDirectory(prefix="archive_audio_") as tmpdir:
                ext = "mp3"
                if ".ogg" in arch_url.lower():
                    ext = "ogg"
                elif ".flac" in arch_url.lower():
                    ext = "flac"
                tmp_input = os.path.join(tmpdir, f"input.{ext}")
                tmp_wav = os.path.join(tmpdir, "output.wav")
                with open(tmp_input, "wb") as f:
                    f.write(dl.content)
                subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp_input, "-ar", "44100", "-ac", "1", tmp_wav],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
                )
                if os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 1000:
                    os.makedirs("output", exist_ok=True)
                    shutil.copy(tmp_wav, out_path)
                    print(f"[Music] Using Internet Archive Audio track → {out_path}")
                    return out_path
    except Exception as exc:
        print(f"[Music] Internet Archive audio fallback failed ({exc})")

    # ── Fallback: procedural ambient generation ──────────────────────────────
    print(f"Generating procedural ambient background music ({duration_seconds}s)...")
    os.makedirs("output", exist_ok=True)

    progression = random.choice(_PROGRESSIONS)
    chord_dur = 4.0
    loop = np.concatenate([_chord(r, q, chord_dur) for r, q in progression])
    reps = int(np.ceil(duration_seconds * SAMPLE_RATE / len(loop))) + 1
    track = np.tile(loop, reps)[: int(duration_seconds * SAMPLE_RATE)]
    # Tick every 0.5s (120 BPM) for high-tension pacing
    tick_interval = int(0.5 * SAMPLE_RATE)
    clock_ticks = _ticking_clock(len(track), tick_interval)
    track = track * 0.45 + clock_ticks


    track = track / (np.max(np.abs(track)) + 1e-9) * 0.65
    track_int16 = (track * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(track_int16.tobytes())
    print(f"Procedural music saved ({progression})")
    return out_path
