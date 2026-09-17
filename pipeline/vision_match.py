import base64
import io
import json
from PIL import Image
from pipeline.gemini import _post_with_rotation
from pipeline.config import GEMINI_FLASH, GEMINI_API_BASE
try:
    from pipeline.config import GEMINI_FLASH_BACKUP
except ImportError:
    GEMINI_FLASH_BACKUP = "gemini-3.1-flash-lite"

def _shrink(img_bytes: bytes, max_dim: int = 768) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _heuristic_frame_check(frames: list[bytes], topic: str = "", narration: str = "", query: str = "") -> tuple[bool, str]:
    """
    Performs fast local PIL/NumPy heuristic check on frame bytes:
    - Rejects pure black screens
    - Rejects blank white slides / tutorial screens
    - Rejects low-contrast murky frames (e.g. empty dark vegetation/bushes) when wildlife is described
    """
    try:
        import numpy as np
        combined_text = f"{topic} {narration} {query}".lower()
        is_wildlife = any(k in combined_text for k in [
            "rat", "rodent", "beetle", "ant", "snake", "worm", "shark", "squid", "spider", "bird", "fish",
            "animal", "mammal", "predator", "insect", "frog", "elephant", "hyena", "creature", "organism"
        ])

        for idx, f_bytes in enumerate(frames):
            im = Image.open(io.BytesIO(f_bytes)).convert("L")
            arr = np.array(im)
            mean_lum = float(arr.mean())
            std_lum = float(arr.std())

            # 1. Pure black or flat solid color (monochrome / blank canvas)
            if std_lum < 9.5:
                return False, f"Heuristic reject: Flat solid/blank screen in frame {idx} (mean={mean_lum:.1f}, std={std_lum:.1f})"
            if mean_lum < 8.0 and std_lum < 12.0:
                return False, f"Heuristic reject: Pure black screen in frame {idx} (mean={mean_lum:.1f})"

            # 2. Blank white screen / slide
            if (mean_lum > 205.0 and std_lum < 35.0) or float(np.mean(arr > 225)) > 0.55:
                return False, f"Heuristic reject: Blank white slide/screen in frame {idx} (mean={mean_lum:.1f}, frac_white={np.mean(arr>225):.2f})"

            # 3. Murky low-contrast dark frame (e.g. empty night-vision vegetation) when focal animal described
            p10, p90 = float(np.percentile(arr, 10)), float(np.percentile(arr, 90))
            contrast = p90 - p10
            if is_wildlife and contrast < 40.0 and mean_lum < 80.0:
                return False, f"Heuristic reject: Murky low-contrast empty frame {idx} (contrast={contrast:.1f}) for wildlife topic"

        return True, "Passed local heuristic sanity check"
    except Exception as e:
        return True, f"Heuristic check bypassed ({e})"

def _parse_vision_json(raw: str) -> dict:
    import re
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Fix unquoted keys: e.g. { best_index: ... } -> { "best_index": ... }
    fixed = re.sub(r'(?<=[{,\s])([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', cleaned)
    # Replace single quotes around values
    fixed = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', fixed)
    # Strip trailing commas
    fixed = re.sub(r',\s*([\]}])', r'\1', fixed)
    try:
        return json.loads(fixed)
    except Exception:
        pass
    res = {}
    m_idx = re.search(r'"?best_index"?\s*:\s*(\d+)', cleaned)
    if m_idx:
        res["best_index"] = int(m_idx.group(1))
    m_found = re.search(r'"?match_found"?\s*:\s*(true|false)', cleaned, re.IGNORECASE)
    if m_found:
        res["match_found"] = m_found.group(1).lower() == "true"
    m_conf = re.search(r'"?confidence"?\s*:\s*(\d+)', cleaned)
    if m_conf:
        res["confidence"] = int(m_conf.group(1))
    m_scores = re.search(r'"?candidate_scores"?\s*:\s*\[([0-9,\s]+)\]', cleaned)
    if m_scores:
        try:
            res["candidate_scores"] = [int(s.strip()) for s in m_scores.group(1).split(",") if s.strip().isdigit()]
        except Exception:
            pass
    m_reason = re.search(r'"?reject_reason"?\s*:\s*"([^"]*)"', cleaned)
    if m_reason:
        res["reject_reason"] = m_reason.group(1)
    m_valid = re.search(r'"?is_valid"?\s*:\s*(true|false)', cleaned, re.IGNORECASE)
    if m_valid:
        res["is_valid"] = m_valid.group(1).lower() == "true"
    return res

def vision_rank_broll(
    thumbnails: list[bytes],
    narration: str,
    query: str,
    topic: str = "",
) -> tuple[int | None, bool]:
    """
    Scores candidate B-roll thumbnails against the EXACT narration sentence and video topic.
    Ranks candidates by semantic fit, not first-provider wins.
    Returns (best_index, match_found).
    Strict zero-score rejection on cosplayers, car showrooms, modern dancers, plush toys, crypto screens,
    and unrelated terrestrial analogies (factories, foundries, sunsets, offices) on space/nature topics.
    """
    if not thumbnails:
        return None, False

    import os
    if os.environ.get("BYPASS_VISION_MATCH") == "1":
        print("[VisionMatch] Bypassing Vision Match (BYPASS_VISION_MATCH=1). Accepting index 0.")
        return 0, True

    # Build the strict matching prompt with airtight zero-score banlist
    topic_header = f"VIDEO TOPIC: \"{topic}\"\n" if topic else ""
    prompt_text = (
        f"{topic_header}"
        f"NARRATION (exact sentence for this video segment):\n"
        f"\"{narration}\"\n\n"
        f"SEARCH QUERY used: \"{query}\"\n\n"
        f"You are evaluating {len(thumbnails)} candidate B-roll image(s) (indexed 0 to {len(thumbnails) - 1}) for the above narration and topic.\n"
        f"Note: Some candidate images may be a horizontal collage showing 3 sequential frames from the same video.\n\n"
        f"SCORING RULES — read carefully:\n"
        f"   - FANTASY / AI SLOP / CGI: ZERO-SCORE REJECT ANY fantasy CGI art, cloaked figures/warlocks/wizards walking in mist, fantasy demons, apocalyptic dark clouds, anime, or video game graphics.\n"
        f"   - STATIC AI IMAGES / POLLINATIONS SLOP: ZERO-SCORE REJECT static 2D drawings, AI-generated synthetic paintings, floating mandalas, or still illustrations. REAL VIDEO MOTION IS MANDATORY.\n"
        f"   - 2D CARTOONS & DOODLES: ZERO-SCORE REJECT ANY 2D cartoon animation, smiling/crying animated blobs/emojis, children's educational drawings, or comic doodles.\n"
        f"   - TOYS, PLASTIC MODELS & PROPS: ZERO-SCORE REJECT plastic toys, desk globes wrapped in bags, miniature dioramas, doll figures, or handmade fake props.\n"
        f"   - STATIONARY 3D STOCK RENDERS & ABSTRACT SHAPES: ZERO-SCORE REJECT completely stationary 3D rendered pill bottles, abstract 3D floating rings/text, or generic spinning DNA helices floating in dark void.\n"
        f"   - GENERIC WALLS & ROOMS: ZERO-SCORE REJECT plain beige/white/gray walls, empty apartment/office rooms, plain ceilings, or blurry indoor backgrounds.\n"
        f"   - CARTOON & FANTASY ANALOGIES: ZERO-SCORE REJECT cartoon characters, superheroes, or fantasy monsters used as analogies for biology or physics.\n"
        f"   - STRICT ORGANISM & PHYSICAL ENTITY IDENTITY (SCORE 0 REJECT):\n"
        f"     If the topic or narration specifies a distinct organism, animal, machine, or artifact (e.g. beetle, shark, octopus, owl, ant, tunnel boring machine, submarine, trebuchet), ANY candidate showing a completely different organism or entity (e.g. showing a fly, dragonfly, grasshopper, fish, bird, or human worker when topic is a beetle) MUST BE GIVEN SCORE 0 (STRICT REJECT).\n"
        f"     Showing a frog catching a FLY when the narration is about a BEETLE escaping is an absolute fatal failure -> SCORE 0.\n"
        f"     Showing empty scenery, landscape, or pond with NO focal organism -> SCORE 0.\n"
        f"   - REAL-WORLD APPARATUS, LABS & MACHINES: ACCEPT authentic contextual documentary footage (e.g. quantum computers, cryogenic dilution refrigerators, cleanroom laboratories, optical lasers, vacuum chambers, oscilloscopes, supercomputers, observatories, geological formations, natural habitats, construction machinery) as HIGH-VALUE VALID MATCHES (scores 80-95)! Do not reject real-world laboratory or engineering apparatus simply because theoretical concepts are microscopic or invisible!\n"
        f"   - UNRELATED TERRESTRIAL ANALOGIES: If video topic is SPACE, ASTRONOMY, or PLANETS, ZERO-SCORE REJECT ANY terrestrial Earth scenes, factories, foundries, metal smelting, blast furnaces, industrial machinery, modern city streets, cars, beaches, sunsets, or modern offices.\n"
        f"   - UNRELATED INDUSTRIAL/OFFICE/CAR SCENES IN NATURE: If video topic is NATURE, WILDLIFE, or DEEP SEA, ZERO-SCORE REJECT modern offices, factory floors, city traffic, paved roads, cars driving in rain/water, or commercial electronics. Narration metaphors like 'chemical flood' or 'toxic rush' MUST NOT be matched to literal rainstorms, puddles, or cars!\n"
        f"   - MODERN ANACHRONISMS IN ANCIENT HISTORY: If video topic is ANCIENT / MEDIEVAL HISTORY, ZERO-SCORE REJECT modern concrete dams, modern suspension bridges, electrical power lines, modern highways, electric streetlamps, or tourists in modern clothing.\n"
        f"   - COMPUTER SCREENS & DESKTOPS IN PHYSICAL SCIENCE: If video topic is PHYSICS, CHEMISTRY, GEOLOGY, or BIOLOGY, ZERO-SCORE REJECT desktop window screencasts (Windows 7/10, WinRAR, MATLAB, browser windows), command prompt consoles, or personal computer monitor recordings.\n"
        f"   - ANY candidate showing cosplayers, LARP, amateur costume roleplay, Comic-Con footage, plastic props/armor, or amateur fantasy reenactments.\n"
        f"   - ANY candidate showing modern car showrooms, indoor car dealerships, vehicle sales floors, or indoor auto expos.\n"
        f"   - ANY candidate showing indoor modern dancers, contemporary choreography, dance studio rehearsals, stage routines, or ballroom dancing.\n"
        f"   - ANY candidate showing stuffed toys, plushies, puppet animals, toy jungles, or kid playsets when narration is financial, economic, business, or serious factual news.\n"
        f"   - ANY candidate showing crypto trading charts, candlestick charts, stock tickers, or day-trading screens when narration is about nature, wildlife, geography, biology, space, or history.\n"
        f"   - ANY candidate showing generic VJ party particle loops, EDM tunnel visualizers, neon DJ background loops, disco/rave graphics, or abstract motion graphics lacking physical real-world relevance.\n"
        f"   - FULL-SCREEN SLIDES & TUTORIALS: Reject pure PowerPoint presentation slides, software tutorials, or pure text documents. NOTE: YouTube candidate thumbnails often feature title text or headlines overlaid on genuine video footage. DO NOT zero-score reject a candidate thumbnail solely because of overlaid title lettering if the underlying visual represents the subject!\n"
        f"   - TALKING HEADS: Reject candidates where a vlogger/podcaster/interview facecam fills the screen talking directly to camera with no documentary B-roll content.\n"
        f"   - ANY candidate showing animated channel intro stingers, opening bumper logos, or 'like & subscribe' graphics.\n"
        f"   - ANY candidate showing generic corporate stock models, smiling office workers, generic handshakes, modern boardroom meetings, or staged actors when discussing science, history, nature, or engineering.\n"
        f"   - ANY candidate showing generic glowing particle soups, abstract blue light tunnels, or decorative stock graphics with zero concrete physical relevance.\n"
        f"   - MODERN INDOOR CIVILIAN STOCK & DIY CRAFTS IN HISTORY: If topic is ANCIENT / MEDIEVAL HISTORY, ZERO-SCORE REJECT modern people in casual civilian clothes (t-shirts, jeans, hoodies) indoors, craft tables, or DIY workshops snapping wooden sticks or holding modern office items.\n"
        f"   - GENERIC RUBBLE & GRAVEL IN MECHANICAL WEAPONRY: When narration describes metallurgy, spear shanks, or weapon engineering, ZERO-SCORE REJECT blurry piles of stones, gravel, dirt, or ceramic rubble.\n"
        f"2. High-quality authentic documentary footage, NASA/ESA telemetry, real-world science apparatus, historical archival media, living nature specimens, and detailed schematics MUST be prioritized (scores 85-98).\n"
        f"3. Score every candidate from 0-100:\n"
        f"   - 85-100: exact physical subject or highly specific real-world match (authentic archival clip, real scientific apparatus, documentary specimen, or precise 3D engineering render)\n"
        f"   - 75-84: strong contextual/thematic physical or documentary match of the main subject\n"
        f"   - 0-74: generic stock filler, symbolic placeholder, talking heads, blank wall, cartoon analogy, or unrelated topic (REJECT)\n"
        f"4. Set match_found=false whenever the best candidate scores below 70 or triggers any ban rule.\n\n"
        f"Return ONLY valid JSON (no markdown):\n"
        f'{{"best_index": <int or null>, '
        f'"match_found": <bool>, '
        f'"confidence": <0-100 int>, '
        f'"candidate_scores": [<0-100 int for each candidate>], '
        f'"reject_reason": \"<why rejected, or empty string if accepted>\"}}\n\n'
        f"Set match_found=true only if confidence >= 70 and ban rules are completely clear."
    )

    parts = [{"text": prompt_text}]

    for t in thumbnails:
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64.b64encode(_shrink(t)).decode(),
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 400},
    }

    models_to_try = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.6-flash",
        GEMINI_FLASH,
        GEMINI_FLASH_BACKUP,
        "gemini-3.7-flash",
    ]

    resp = None
    last_err = None
    for model_name in models_to_try:
        url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={{key}}"
        try:
            resp = _post_with_rotation(url, payload, timeout=20)
            if resp and resp.status_code == 200:
                cand = resp.json().get("candidates", [{}])[0]
                text_val = cand.get("content", {}).get("parts", [{}])[0].get("text", "")
                if text_val:
                    break
        except Exception as e:
            last_err = e
            continue

    if resp is None or resp.status_code != 200:
        print(f"[VisionMatch] Vision API unavailable ({last_err}). Signaling api_unavailable (None, None).")
        return None, None

    try:
        cand = resp.json().get("candidates", [{}])[0]
        raw = cand.get("content", {}).get("parts", [{}])[0].get("text", "")
        if not raw:
            return None, False
        data = _parse_vision_json(raw)

        idx        = data.get("best_index")
        found      = bool(data.get("match_found", False))
        confidence = int(data.get("confidence", 0))
        scores     = data.get("candidate_scores", [])
        reason     = data.get("reject_reason", "")

        if isinstance(scores, list) and scores:
            print(f"[VisionMatch] Candidate scores: {scores}")
        if reason:
            print(f"[VisionMatch] Note: {reason} (confidence={confidence})")

        # Find highest scoring candidate with score >= 70 from candidate_scores list
        best_candidate_idx = None
        highest_score = 0
        if isinstance(scores, list) and len(scores) > 0:
            for s_idx, score in enumerate(scores):
                if s_idx >= len(thumbnails):
                    break
                if isinstance(score, (int, float)) and score >= 70 and score > highest_score:
                    highest_score = score
                    best_candidate_idx = s_idx

        if best_candidate_idx is not None:
            quality = "flawless" if highest_score >= 85 else "strong"
            print(f"[VisionMatch] Accepted {quality} index {best_candidate_idx} (score={highest_score})")
            return best_candidate_idx, True

        # Check model's best_index if confidence is valid
        if found and isinstance(idx, int) and 0 <= idx < len(thumbnails) and confidence >= 70:
            quality = "flawless" if confidence >= 85 else "strong"
            print(f"[VisionMatch] Accepted {quality} index {idx} (confidence={confidence})")
            return idx, True

        # ABSOLUTE REJECTION: Do NOT force Candidate 0 if all candidates score < 70
        print(f"[VisionMatch] All candidate scores below 70 (scores={scores}). Strictly rejecting batch to force authentic archival/synthesis fallback.")
        return None, False

    except Exception as e:
        print(f"[VisionMatch] Vision JSON parse note: {e}. Strictly rejecting batch to force authentic fallback.")
        return None, False


def verify_video_frames(
    frames: list[bytes],
    narration: str,
    query: str,
    topic: str = "",
) -> tuple[bool, str]:
    """
    Performs deep multi-frame visual verification on downloaded candidate video frames.
    Strictly rejects:
    1. Talking heads, podcast hosts, bedroom vloggers, faces talking directly to camera.
    2. Slide decks, PowerPoint bullets, presentation text, blackboards, software tutorials.
    3. Logo bumpers, channel intros, 'like and subscribe' graphics, watermarks.
    4. Completely unrelated visual content to the narration / topic.
    Returns (is_valid, reason).
    """
    if not frames:
        return False, "No frames to inspect"

    import os
    if os.environ.get("BYPASS_VISION_MATCH") == "1":
        return True, "Vision match bypassed"

    prompt_text = (
        f"VIDEO TOPIC: \"{topic}\"\n"
        f"SEGMENT NARRATION: \"{narration}\"\n"
        f"SEARCH QUERY: \"{query}\"\n\n"
        f"You are inspecting {len(frames)} actual video frame(s) extracted from a candidate B-roll clip.\n"
        f"Evaluate whether these frames are high-quality, authentic documentary B-roll, or if they must be REJECTED.\n\n"
        f"CRITICAL REJECTION RULES (Return is_valid=false):\n"
        f"1. TALKING HEADS: Reject if the video shows a person speaking to the camera, YouTuber, vlogger, podcast presenter, or interview facecam.\n"
        f"2. FANTASY / AI SLOP / CGI: Reject fantasy CGI art, cloaked warlocks/wizards, demons, apocalyptic clouds, anime, or video game graphics.\n"
        f"3. 2D CARTOONS & DOODLES: Reject 2D cartoon animations, smiling/crying animated blobs/emojis, or childish educational drawings.\n"
        f"4. TOYS & DIORAMAS: Reject plastic desk globes, objects wrapped in trash bags, toy cars, or miniature fake props.\n"
        f"5. STATIONARY 3D MODELS: Reject completely motionless 3D rendered bottles, jars, or generic spinning DNA helices floating in dark void.\n"
        f"6. SLIDES & TEXT: Reject if the frame is a PowerPoint slide, presentation bullet points, lecture blackboard, title card, text document, or tutorial screen.\n"
        f"7. INTROS & BUMPERS: Reject channel intro screens, animated logos, creator stingers, watermark graphics, or 'subscribe' animations.\n"
        f"8. UNRELATED SCENES: Reject footage that has no conceptual or physical connection to the topic/narration (e.g. car showroom, modern office, factory floor when topic is deep ocean or astronomy).\n"
        f"9. GENERIC WALLS & ROOMS: Reject plain blank/beige/white/gray walls, empty apartment/office rooms, plain ceilings, or blurry indoor backgrounds.\n"
        f"10. GENERIC PEOPLE & PHONES: Reject back-of-head or over-the-shoulder shots of unidentified people looking around, generic hands holding smartphones/tablets, or staged actors with electronics.\n"
        f"11. SYMBOLIC ANALOGIES FOR BIOLOGY / SCIENCE: Reject cartoon mice/superheroes used as analogies for biological processes or antidote production, generic whole animals (e.g. green tree snake) when narration describes microscopic blood/molecules/antibodies/venom breakdown, and generic outer-space planets when narration describes Earth's mantle or core.\n"
        f"12. REAL-WORLD APPARATUS & CONTEXTUAL LAB FOOTAGE: DO NOT reject real-world scientific apparatus, laboratories, cleanrooms, oscilloscopes, lasers, microscopes, machinery, or specimens simply because theoretical/abstract concepts (e.g. quantum energy, relativity, dark matter) are invisible! High-tech laboratory apparatus, machinery, engineering setups, natural habitats, and documentary field footage ARE HIGH-VALUE VALID MATCHES (Score 80-95).\n"
        f"13. ELECTRONICS & WORKBENCHES: Only reject soldering irons and loose consumer circuit boards when the topic is strictly pure biology, wildlife, or ancient history. If the topic is PHYSICS, COMPUTING, ENGINEERING, TELECOMMUNICATIONS, or ADVANCED TECH, electronics, cleanroom equipment, and quantum apparatus ARE HIGHLY RELEVANT AND ACCEPTABLE (Score 85-95).\n"
        f"14. CAMERA & MECHANICAL REPAIR: Reject camera sensor cleaning, lens disassembly, watch repair, or mechanic tools when topic is biology/nature/science.\n"
        f"15. FANTASY BEASTS & MONSTERS: Reject werewolves, minotaurs, mythical monsters, or CGI beast creatures when topic is scientific or biological organisms.\n"
        f"16. STRICT ORGANISM & PHYSICAL SUBJECT IDENTITY (MANDATORY REJECT -> is_valid=false):\n"
        f"    If the topic or narration describes a specific creature, organism, or machine (e.g. water beetle, shark, ant, turbine, tunnel boring machine), the frames MUST actually depict that specific creature, machine, or direct physical mechanism. Reject immediately (is_valid=false) if frames show a different organism (e.g. fly, grasshopper, dragonfly when searching for beetle) or generic scenery/landscape without the focal creature.\n"
        f"17. EMPTY VEGETATION / HABITAT WITHOUT ORGANISM (MANDATORY REJECT -> is_valid=false):\n"
        f"    If the narration or topic names an animal or organism (e.g. rat, rodent, beetle, squid, worm, ant, snake, elephant, predator), the organism MUST be clearly visible and identifiable! Reject immediately (is_valid=false) if the frame only depicts empty bushes, dark night-vision vegetation without the animal, blurry dirt, a vehicle/jeep without the animal, an empty cage, or distant blurred scenery.\n"
        f"18. MODERN ANACHRONISMS IN ANCIENT/MEDIEVAL HISTORY (MANDATORY REJECT -> is_valid=false):\n"
        f"    If the topic or narration describes ancient or medieval history (e.g. Akkad, Rome, Greece, Bronze Age, siege weapons), strictly reject modern steel combat helmets, helmets with bullet holes, military surplus, firearms, modern concrete dams/bridges, modern asphalt roads, electric streetlights, power lines, modern motor vehicles, and tourists in modern clothing.\n"
        f"19. DOMESTIC KITCHEN & BAKING (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject home cooking, kitchen whisks, mixing bowls, cake batter, measuring cups, and kitchen counters when the topic is industrial engineering, mining, chemistry, or commodity syndicates.\n"
        f"20. BLANK / SOLID VOID SCREENS (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject frames that are >60% solid white, solid gray, or empty presentation slides with minimal icons or text.\n"
        f"21. METAPHOR LEAKS IN NATURE / WILDLIFE (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject modern cars, vintage 1950s automobiles, paved roads, rain gutters, city puddles, or weather rainstorms when narration discusses biological processes (such as 'chemical flood', 'potassium rush', 'nerve signal', 'toxic blast'). Narration metaphors MUST NOT be matched to literal rainstorms, puddles, or cars!\n"
        f"22. COMPUTER DESKTOPS & SCREENS IN SCIENCE & BIOLOGY (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject Windows 7/XP/10 desktop recordings, WinRAR windows, MATLAB GUI screencasts, command prompt consoles, or personal computer monitor recordings when topic is physical science, chemistry, geology, or biology.\n"
        f"23. VINTAGE MONOCHROME HOME MOVIES IN MODERN NICHES (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject 1940s-1950s grainy black-and-white public service announcements, vintage home movies, or monochrome cartoons unless the topic is explicitly vintage 20th-century history.\n"
        f"24. CAMERA FLOOR TILT / EMPTY GROUND OR TURF (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject frames that primarily depict blurry grass, artificial turf, floor tiles, asphalt, or camera tilting down toward the ground without the key subject clearly visible.\n"
        f"25. CLASSROOM BIOLOGY MICROSCOPES IN QUANTUM & ASTROPHYSICS (MANDATORY REJECT -> is_valid=false):\n"
        f"    If topic is quantum mechanics, photons, interferometers, laser physics, or astrophysics, STRICTLY REJECT basic optical/light microscopes with rotating objective turrets, glass slides, and hand-focus knobs. (Note: Scanning electron microscopes SEM/TEM, scanning tunneling microscopes STM, laser optical tables, and cryostat chambers ARE VALID).\n"
        f"26. SPEED / BULLET METAPHOR LEAKS IN WILDLIFE (MANDATORY REJECT -> is_valid=false):\n"
        f"    If narration uses speed metaphors like 'faster than a bullet', 'hits like lightning', or 'explodes like a bomb' to describe an animal or insect, STRICTLY REJECT literal bullets, ammunition, gun ranges, artillery, or weather lightning! The footage MUST show the actual organism in high-speed macro motion.\n"
        f"27. CHEAP 3D CAD SCHEMATICS & WIREFRAME RENDERS (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject low-poly 3D models, untextured CAD schematics, spinning wireframe diagrams, or amateur CGI animations. (Note: High-end photorealistic mechanical cutaways, supercomputer CFD fluid dynamic simulations from NASA/aerospace institutions, and authentic physical hardware ARE ACCEPTABLE).\n"
        f"28. HEAVY PIXELATION, COMPRESSION ARTIFACTS & UNRECOGNIZABLE BLUR (MANDATORY REJECT -> is_valid=false):\n"
        f"    Reject footage that is an incomprehensible, artifact-heavy, low-bitrate blur or dark muddy cyan/green mess where mechanical parts or organisms cannot be clearly distinguished. (Note: Authentic high-speed optical motion blur of a fast organism or machine is acceptable if the subject is clearly recognizable).\n"
        f"29. MODERN INDOOR CIVILIAN STOCK & DIY CRAFTS IN HISTORY NICHES (MANDATORY REJECT -> is_valid=false):\n"
        f"    If the topic or narration describes ancient, medieval, or historical warfare/events, STRICTLY REJECT modern people in casual civilian clothing (t-shirts, jeans, hoodies, wristwatches) in indoor living rooms, craft tables, or DIY hobby workshops snapping wooden dowels/sticks or manipulating modern items. Visuals MUST be authentic historical reenactments in period garb, museum weapons/artifacts, archaeological excavations, or historical schematics.\n"
        f"30. GENERIC RUBBLE, STONES & GRAVEL IN MECHANICAL WEAPONRY (MANDATORY REJECT -> is_valid=false):\n"
        f"    When narration describes metallurgy, weapons engineering, spear joints, or metal failure (e.g. bending iron shanks, rivets, blade forging), STRICTLY REJECT blurry piles of crushed gravel, stones, dirt clods, or ceramic debris! Footage MUST depict authentic metal forging, blacksmithing anvils, weapon replicas, or museum arms.\n\n"
        f"ACCEPTABLE (Return is_valid=true):\n"
        f"Authentic documentary footage, archival footage, machinery, scientific apparatus, specimens, space imagery, or relevant historical footage that directly depicts the subject or mechanism described in the narration.\n\n"
        f"Return ONLY valid JSON (no markdown):\n"
        f'{{"is_valid": <bool>, "confidence": <0-100 int>, "reject_reason": "<brief explanation if rejected, else empty string>"}}'
    )

    # Fast local pre-check to reject pure black or blank white frames instantly
    h_ok, h_reason = _heuristic_frame_check(frames, topic=topic, narration=narration, query=query)
    if not h_ok:
        print(f"[VisionMatch] Candidate frame pre-check REJECTED: {h_reason}")
        return False, h_reason

    parts = [{"text": prompt_text}]
    for f_bytes in frames:
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64.b64encode(_shrink(f_bytes)).decode(),
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 250},
    }

    models_to_try = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.6-flash",
        GEMINI_FLASH,
        GEMINI_FLASH_BACKUP,
        "gemini-3.7-flash",
    ]

    resp = None
    last_err = None
    for model_name in models_to_try:
        url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={{key}}"
        try:
            resp = _post_with_rotation(url, payload, timeout=20)
            if resp and resp.status_code == 200:
                cand = resp.json().get("candidates", [{}])[0]
                text_val = cand.get("content", {}).get("parts", [{}])[0].get("text", "")
                if text_val:
                    break
        except Exception as e:
            last_err = e
            continue

    if resp is None or resp.status_code != 200:
        if not h_ok:
            print(f"[VisionMatch] Vision API down & candidate REJECTED by heuristic check: {h_reason}")
            return False, h_reason
        print(f"[VisionMatch] Vision API models unavailable (last_err={last_err}). Strictly REJECTING candidate to prevent visual mismatches.")
        return False, f"Vision verification unavailable - strictly rejected unverified candidate ({last_err})"

    try:
        cand = resp.json().get("candidates", [{}])[0]
        raw = cand.get("content", {}).get("parts", [{}])[0].get("text", "")
        if not raw:
            return False, "Vision model returned empty response parts"
        data = _parse_vision_json(raw)
        is_valid = bool(data.get("is_valid", False))
        conf = int(data.get("confidence", 0))
        reason = data.get("reject_reason", "")
        if not is_valid:
            print(f"[VisionMatch] Frame verification REJECTED: {reason}")
            return False, reason or "Rejected by vision gate"
        if conf < 70:
            print(f"[VisionMatch] Frame verification rejected due to low confidence: {conf}%")
            return False, f"Low visual confidence ({conf}%)"
        print(f"[VisionMatch] Frame verification PASSED: confidence={conf}%")
        return True, "Vision verified"
    except Exception as e:
        return False, f"Vision frame verification parse note: {e}. Strictly rejecting unverified clip."

