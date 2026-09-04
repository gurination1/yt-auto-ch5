import base64
import io
import json
from PIL import Image
from pipeline.gemini import _post_with_rotation
from pipeline.config import GEMINI_FLASH, GEMINI_API_BASE

def _shrink(img_bytes: bytes, max_dim: int = 768) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()

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
        f"1. CRITICAL ZERO-SCORE REJECTION (SCORE = 0 IMMEDIATELY & REJECT):\n"
        f"   - UNRELATED TERRESTRIAL ANALOGIES: If video topic is SPACE, ASTRONOMY, or PLANETS, ZERO-SCORE REJECT ANY terrestrial Earth scenes, factories, foundries, metal smelting, blast furnaces, industrial machinery, modern city streets, cars, beaches, sunsets, or modern offices. (e.g. showing factory molten metal when discussing planetary cores or diamond rain is an UNACCEPTABLE mismatch).\n"
        f"   - UNRELATED INDUSTRIAL/OFFICE SCENES: If video topic is NATURE, WILDLIFE, or DEEP SEA, ZERO-SCORE REJECT modern offices, factory floors, city traffic, or commercial electronics.\n"
        f"   - ANY candidate showing cosplayers, LARP, amateur costume roleplay, Comic-Con footage, plastic props/armor, or amateur fantasy reenactments.\n"
        f"   - ANY candidate showing modern car showrooms, indoor car dealerships, vehicle sales floors, or indoor auto expos.\n"
        f"   - ANY candidate showing indoor modern dancers, contemporary choreography, dance studio rehearsals, stage routines, or ballroom dancing.\n"
        f"   - ANY candidate showing stuffed toys, plushies, puppet animals, toy jungles, or kid playsets when narration is financial, economic, business, or serious factual news.\n"
        f"   - ANY candidate showing crypto trading charts, candlestick charts, stock tickers, or day-trading screens when narration is about nature, wildlife, geography, biology, space, or history.\n"
        f"   - ANY candidate showing generic VJ party particle loops, EDM tunnel visualizers, neon DJ background loops, disco/rave graphics, or abstract motion graphics lacking physical real-world relevance.\n"
        f"   - ANY candidate showing full-screen text, title cards, subtitles, lower-third graphics, channel logos, or text-only slides from the source video.\n"
        f"   - ANY candidate showing generic corporate stock models, smiling office workers, generic handshakes, modern boardroom meetings, or staged actors when discussing science, history, nature, or engineering.\n"
        f"   - ANY candidate showing generic glowing particle soups, abstract blue light tunnels, or decorative stock graphics with zero concrete physical relevance.\n"
        f"2. High-quality authentic documentary footage, NASA/ESA telemetry, real-world science apparatus, historical archival media, living nature specimens, and detailed schematics MUST be prioritized (scores 85-98).\n"
        f"3. Score every candidate from 0-100:\n"
        f"   - 90-100: exact physical subject or highly specific real-world match (authentic archival clip, real scientific apparatus, documentary specimen, or precise 3D engineering render)\n"
        f"   - 75-89: strong contextual/thematic physical or documentary match of the main subject\n"
        f"   - 50-74: usable fallback active visual related to the topic\n"
        f"   - 0-49: generic stock filler, talking heads, static text slide, title card, black screen, or unrelated topic\n"
        f"4. Set match_found=false whenever the best candidate scores below 50 or triggers any rule in Section 1.\n\n"
        f"Return ONLY valid JSON (no markdown):\n"
        f'{{"best_index": <int or null>, '
        f'"match_found": <bool>, '
        f'"confidence": <0-100 int>, '
        f'"candidate_scores": [<0-100 int for each candidate>], '
        f'"reject_reason": \"<why rejected, or empty string if accepted>\"}}\n\n'
        f"Set match_found=true only if confidence >= 50 and Section 1 bans are clear."
    )

    parts = [{"text": prompt_text}]

    for t in thumbnails:
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": base64.b64encode(_shrink(t)).decode(),
            }
        })

    url = f"{GEMINI_API_BASE}/models/{GEMINI_FLASH}:generateContent?key={{key}}"
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.05,   # very low — deterministic judgment
            "responseMimeType": "application/json",
        },
    }

    try:
        resp = _post_with_rotation(url, payload, timeout=60)
        raw  = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(raw)

        idx        = data.get("best_index")
        found      = bool(data.get("match_found", False))
        confidence = int(data.get("confidence", 0))
        scores     = data.get("candidate_scores", [])
        reason     = data.get("reject_reason", "")

        if isinstance(scores, list) and scores:
            print(f"[VisionMatch] Candidate scores: {scores}")
        if reason:
            print(f"[VisionMatch] Note: {reason} (confidence={confidence})")

        # Find highest scoring candidate with score >= 50 from candidate_scores list
        best_candidate_idx = None
        highest_score = 0
        if isinstance(scores, list) and len(scores) == len(thumbnails):
            for s_idx, score in enumerate(scores):
                if isinstance(score, (int, float)) and score >= 50 and score > highest_score:
                    highest_score = score
                    best_candidate_idx = s_idx

        if best_candidate_idx is not None:
            quality = "strong" if highest_score >= 70 else "usable"
            print(f"[VisionMatch] Accepted {quality} index {best_candidate_idx} (score={highest_score})")
            return best_candidate_idx, True

        # Check model's best_index if confidence is valid
        if found and isinstance(idx, int) and 0 <= idx < len(thumbnails) and confidence >= 50:
            quality = "strong" if confidence >= 70 else "usable"
            print(f"[VisionMatch] Accepted {quality} index {idx} (confidence={confidence})")
            return idx, True

        # ABSOLUTE REJECTION: Do NOT force Candidate 0 if all candidates score < 50
        print(f"[VisionMatch] All candidate scores below 50 (scores={scores}). Strictly rejecting batch.")
        return None, False

    except Exception as e:
        print(f"[VisionMatch] API unavailable or error: {e}. Strictly rejecting candidate batch so pipeline falls back to topic visual.")
        return None, False
