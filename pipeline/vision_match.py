import base64
import io
import json
from PIL import Image
from pipeline.gemini import _post_with_rotation
from pipeline.config import GEMINI_FLASH, GEMINI_API_BASE
try:
    from pipeline.config import GEMINI_FLASH_BACKUP
except ImportError:
    GEMINI_FLASH_BACKUP = "gemini-2.5-flash-lite"

def _shrink(img_bytes: bytes, max_dim: int = 768) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()

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
        f"   - 2D CARTOONS & DOODLES: ZERO-SCORE REJECT ANY 2D cartoon animation, smiling/crying animated blobs/emojis, children's educational drawings, or comic doodles.\n"
        f"   - TOYS, PLASTIC MODELS & PROPS: ZERO-SCORE REJECT plastic toys, desk globes wrapped in bags, miniature dioramas, doll figures, or handmade fake props.\n"
        f"   - STATIONARY 3D STOCK RENDERS & ABSTRACT SHAPES: ZERO-SCORE REJECT completely stationary 3D rendered pill bottles, abstract 3D floating rings/text, or generic spinning DNA helices floating in dark void.\n"
        f"   - GENERIC WALLS & ROOMS: ZERO-SCORE REJECT plain beige/white/gray walls, empty apartment/office rooms, plain ceilings, or blurry indoor backgrounds.\n"
        f"   - GENERIC PEOPLE & PHONES: ZERO-SCORE REJECT back-of-head or over-the-shoulder shots of unidentified people looking around, generic hands holding smartphones/tablets, or staged actors with electronics.\n"
        f"   - SYMBOLIC ANALOGIES FOR BIOLOGY / SCIENCE: ZERO-SCORE REJECT cartoon mice/superheroes used as analogies for biological processes or antidote production, generic whole animals (e.g. green tree snake) when narration describes microscopic blood/molecules/antibodies/venom breakdown, and generic outer-space planets when narration describes Earth's mantle or core.\n"
        f"   - UNRELATED TERRESTRIAL ANALOGIES: If video topic is SPACE, ASTRONOMY, or PLANETS, ZERO-SCORE REJECT ANY terrestrial Earth scenes, factories, foundries, metal smelting, blast furnaces, industrial machinery, modern city streets, cars, beaches, sunsets, or modern offices.\n"
        f"   - UNRELATED INDUSTRIAL/OFFICE SCENES: If video topic is NATURE, WILDLIFE, or DEEP SEA, ZERO-SCORE REJECT modern offices, factory floors, city traffic, or commercial electronics.\n"
        f"   - ANY candidate showing cosplayers, LARP, amateur costume roleplay, Comic-Con footage, plastic props/armor, or amateur fantasy reenactments.\n"
        f"   - ANY candidate showing modern car showrooms, indoor car dealerships, vehicle sales floors, or indoor auto expos.\n"
        f"   - ANY candidate showing indoor modern dancers, contemporary choreography, dance studio rehearsals, stage routines, or ballroom dancing.\n"
        f"   - ANY candidate showing stuffed toys, plushies, puppet animals, toy jungles, or kid playsets when narration is financial, economic, business, or serious factual news.\n"
        f"   - ANY candidate showing crypto trading charts, candlestick charts, stock tickers, or day-trading screens when narration is about nature, wildlife, geography, biology, space, or history.\n"
        f"   - ANY candidate showing generic VJ party particle loops, EDM tunnel visualizers, neon DJ background loops, disco/rave graphics, or abstract motion graphics lacking physical real-world relevance.\n"
        f"   - ANY candidate showing full-screen text, title cards, subtitles, lower-third graphics, channel logos, or text-only slides from the source video.\n"
        f"   - ANY candidate showing PowerPoint slides, bullet points, lecture blackboards, or software tutorials.\n"
        f"   - ANY candidate showing talking heads, podcast hosts, bedroom vloggers, or YouTubers talking directly to camera.\n"
        f"   - ANY candidate showing animated channel intro stingers, opening bumper logos, or 'like & subscribe' graphics.\n"
        f"   - ANY candidate showing generic corporate stock models, smiling office workers, generic handshakes, modern boardroom meetings, or staged actors when discussing science, history, nature, or engineering.\n"
        f"   - ANY candidate showing generic glowing particle soups, abstract blue light tunnels, or decorative stock graphics with zero concrete physical relevance.\n"
        f"2. High-quality authentic documentary footage, NASA/ESA telemetry, real-world science apparatus, historical archival media, living nature specimens, and detailed schematics MUST be prioritized (scores 85-98).\n"
        f"3. Score every candidate from 0-100:\n"
        f"   - 85-100: exact physical subject or highly specific real-world match (authentic archival clip, real scientific apparatus, documentary specimen, or precise 3D engineering render)\n"
        f"   - 75-84: strong contextual/thematic physical or documentary match of the main subject\n"
        f"   - 0-74: generic stock filler, symbolic placeholder, talking heads, blank wall, cartoon analogy, or unrelated topic (REJECT)\n"
        f"4. Set match_found=false whenever the best candidate scores below 75 or triggers any ban rule.\n\n"
        f"Return ONLY valid JSON (no markdown):\n"
        f'{{"best_index": <int or null>, '
        f'"match_found": <bool>, '
        f'"confidence": <0-100 int>, '
        f'"candidate_scores": [<0-100 int for each candidate>], '
        f'"reject_reason": \"<why rejected, or empty string if accepted>\"}}\n\n'
        f"Set match_found=true only if confidence >= 75 and ban rules are completely clear."
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
        GEMINI_FLASH,
        GEMINI_FLASH_BACKUP,
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ]

    resp = None
    last_err = None
    for model_name in models_to_try:
        url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={{key}}"
        try:
            resp = _post_with_rotation(url, payload, timeout=60)
            if resp and resp.status_code == 200:
                break
        except Exception as e:
            last_err = e
            continue

    if resp is None or resp.status_code != 200:
        print(f"[VisionMatch] Vision API unavailable or exhausted ({last_err}). Signaling api_unavailable (None, None).")
        return None, None

    try:
        raw  = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
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

        # Find highest scoring candidate with score >= 75 from candidate_scores list
        best_candidate_idx = None
        highest_score = 0
        if isinstance(scores, list) and len(scores) == len(thumbnails):
            for s_idx, score in enumerate(scores):
                if isinstance(score, (int, float)) and score >= 75 and score > highest_score:
                    highest_score = score
                    best_candidate_idx = s_idx

        if best_candidate_idx is not None:
            quality = "flawless" if highest_score >= 85 else "strong"
            print(f"[VisionMatch] Accepted {quality} index {best_candidate_idx} (score={highest_score})")
            return best_candidate_idx, True

        # Check model's best_index if confidence is valid
        if found and isinstance(idx, int) and 0 <= idx < len(thumbnails) and confidence >= 75:
            quality = "flawless" if confidence >= 85 else "strong"
            print(f"[VisionMatch] Accepted {quality} index {idx} (confidence={confidence})")
            return idx, True

        # ABSOLUTE REJECTION: Do NOT force Candidate 0 if all candidates score < 75
        print(f"[VisionMatch] All candidate scores below 75 (scores={scores}). Strictly rejecting batch to force authentic archival/synthesis fallback.")
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
        f"12. DIRECT PHYSICAL CORRELATION: Visual MUST directly portray the concrete physical subject described in narration (microscopy, crystallography, laboratory apparatus, or authentic documentary specimen).\n"
        f"13. ELECTRONICS & WORKBENCHES: Reject soldering irons, printed circuit boards, microchips, electronics lab benches, computer hardware debugging, or wiring when topic is biology/nature/wildlife/astronomy.\n"
        f"14. CAMERA & MECHANICAL REPAIR: Reject camera sensor cleaning, lens disassembly, watch repair, or mechanic tools when topic is biology/nature/science.\n"
        f"15. FANTASY BEASTS & MONSTERS: Reject werewolves, minotaurs, mythical monsters, or CGI beast creatures when topic is scientific or biological organisms.\n\n"
        f"ACCEPTABLE (Return is_valid=true):\n"
        f"Authentic documentary footage, archival footage, natural landscapes, machinery, scientific apparatus, specimens, space imagery, or relevant historical footage.\n\n"
        f"Return ONLY valid JSON (no markdown):\n"
        f'{{"is_valid": <bool>, "confidence": <0-100 int>, "reject_reason": "<brief explanation if rejected, else empty string>"}}'
    )

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
        GEMINI_FLASH,
        GEMINI_FLASH_BACKUP,
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ]

    resp = None
    for model_name in models_to_try:
        url = f"{GEMINI_API_BASE}/models/{model_name}:generateContent?key={{key}}"
        try:
            resp = _post_with_rotation(url, payload, timeout=30)
            if resp and resp.status_code == 200:
                break
        except Exception:
            continue

    if resp is None or resp.status_code != 200:
        return False, f"Vision API unavailable (status={getattr(resp, 'status_code', 'none')}). Strictly rejecting candidate to prevent visual slop."

    try:
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
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

