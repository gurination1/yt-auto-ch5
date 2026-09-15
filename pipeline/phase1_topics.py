import os
import re
import json
from pipeline.config import (
    TOPIC_LOG_SIZE,
    CHANNEL_BOUNDARY,
    CHANNEL_SUBCLUSTERS,
    RICH_FALLBACK_TOPICS,
)
from pipeline.gemini import GeminiClient, _robust_json_loads


def get_keywords(text: str) -> set:
    text = text.lower()
    words = re.findall(r'\b[a-z0-9-]{3,}\b', text)
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "these", "those",
        "how", "why", "what", "who", "whom", "which", "where", "when", "actually",
        "about", "would", "could", "should", "your", "them", "they", "their",
        "reveals", "bizarre", "counterinteractive", "counterintuitive", "little-known", "fact", "science",
        "people", "scientists", "discovered", "discovery", "reveal", "unlocks",
        "unlocked", "unlocking", "understanding", "mechanism", "theory", "phenomenon"
    }
    return {w for w in words if w not in stopwords}


def validate_topic_boundary(topic_text: str, boundary: dict) -> tuple[bool, str]:
    """
    Strictly validates that topic_text belongs to the channel's designated niche
    and does not contain forbidden keywords from other channel domains.
    """
    if not topic_text or len(topic_text.strip()) < 10:
        return False, "Topic text is empty or too short (<10 chars)"

    clean_text = " " + re.sub(r'[^a-z0-9\s-]', ' ', topic_text.lower()) + " "

    for kw in boundary.get("negative_keywords", []):
        kw_clean = kw.lower().strip()
        if not kw_clean:
            continue
        pattern = r'\b' + re.escape(kw_clean) + r'\b'
        if re.search(pattern, clean_text):
            return False, f"Matched forbidden keyword: '{kw}'"

    return True, ""


def is_duplicate(new_topic: str, published: list[str]) -> bool:
    new_keys = get_keywords(new_topic)
    if not new_keys:
        return False

    new_norm = re.sub(r'[^a-z0-9]', '', new_topic.lower())
    for old_topic in published:
        old_norm = re.sub(r'[^a-z0-9]', '', old_topic.lower())
        if new_norm in old_norm or old_norm in new_norm:
            print(f"[Similarity Check] Rejecting topic '{new_topic}' — substring match with: '{old_topic}'")
            return True

        old_keys = get_keywords(old_topic)
        overlap = new_keys.intersection(old_keys)
        if len(overlap) >= 3 or (len(new_keys) > 0 and len(overlap) / len(new_keys) >= 0.4):
            print(f"[Similarity Check] Rejecting topic '{new_topic}' due to overlap {overlap} with: '{old_topic}'")
            return True
    return False


def get_next_fallback_topic(format_type: str, current_subcluster: str, published: list[str], start_idx: int = 0) -> tuple[dict, int]:
    """
    Rotates through RICH_FALLBACK_TOPICS to find a fresh, non-duplicate topic.
    Guarantees no infinite repeating of a single topic.
    """
    total = len(RICH_FALLBACK_TOPICS)
    for offset in range(total):
        idx = (start_idx + offset) % total
        cand = RICH_FALLBACK_TOPICS[idx]
        if cand.get("for_format", "both") in (format_type, "both"):
            if not is_duplicate(cand["topic"], published):
                next_idx = (idx + 1) % total
                cand_copy = dict(cand)
                if not cand_copy.get("subcluster"):
                    cand_copy["subcluster"] = current_subcluster
                return cand_copy, next_idx

    # If all appear in published history, select the least recently used one
    best_idx = start_idx % total
    oldest_pos = float('inf')
    for idx in range(total):
        cand = RICH_FALLBACK_TOPICS[idx]
        topic_str = cand["topic"]
        pos = published.index(topic_str) if topic_str in published else -1
        if pos < oldest_pos:
            oldest_pos = pos
            best_idx = idx

    cand_copy = dict(RICH_FALLBACK_TOPICS[best_idx])
    next_idx = (best_idx + 1) % total
    return cand_copy, next_idx


def select_topic(format_type: str) -> dict:
    # ── 1. Load published topics log ─────────────────────────────────────────
    topic_log_path = "published_topics.json"
    if os.path.exists(topic_log_path):
        try:
            with open(topic_log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                published = data.get("topics", [])
                subcluster_idx = data.get("subcluster_idx", 0)
                fallback_idx = data.get("fallback_idx", 0)
                call_count = data.get("call_count", 0)
        except Exception as e:
            print(f"Warning: Failed to load published topics: {e}")
            published = []; subcluster_idx = 0; fallback_idx = 0; call_count = 0
    else:
        published = []; subcluster_idx = 0; fallback_idx = 0; call_count = 0

    recent_topics = published[-TOPIC_LOG_SIZE:]
    call_count += 1

    # ── 2. Determine active subcluster + trending vs evergreen ──────────────
    current_subcluster = CHANNEL_SUBCLUSTERS[subcluster_idx % len(CHANNEL_SUBCLUSTERS)]
    is_trending = (call_count % 3 != 0)   # 2 out of 3 calls = trending topic

    boundary = CHANNEL_BOUNDARY
    niche_name = boundary["name"]
    allowed_desc = boundary["niche_description"]
    strict_negatives = "\n".join(f"- {rule}" for rule in boundary["strict_negative_constraints"])

    if is_trending:
        topic_instruction = (
            f"Use Google Search to find mind-blowing, verified recent discoveries, breakthroughs, or events from the last 24-48 hours specifically about '{current_subcluster}'. "
            f"Generate 5 TRENDING topics that reveal a startling reality normal people did NOT know but DEEPLY WANT TO KNOW. "
            f"STRICT RULES: Must be a concrete, verified true subject with massive visual curiosity. "
            f"FORBIDDEN: Dry municipal logistics, pavement/freight axle load limits, routine regulatory paperwork, or boring corporate filings. "
            f"Every topic must make an average person say: 'Wait, is that actually real?!'"
        )
    else:
        topic_instruction = (
            f"Generate 5 insanely fascinating, real-world EVERGREEN topics specifically about '{current_subcluster}'. "
            f"CRITICAL REQUIREMENTS: "
            f"1. HIGH-CURIOSITY SECRET: Must reveal a bizarre, shocking, or counter-intuitive secret that 99% of people do NOT know, but ordinary people find deeply fascinating. "
            f"2. FORBIDDEN: Boring bureaucratic logistics (e.g. airport tarmac pavement degradation, freight axle weight limits, routine municipal maintenance) and generic textbook summaries. "
            f"3. REQUIRED: A specific real-world anomaly, unbelievable physical fact, corporate trade secret, or mind-bending paradox. "
            f"4. Easy to understand: A 12-year-old must instantly grasp why it is insane. Zero academic jargon."
        )

    # ── 3. Build Gemini prompt with airtight channel boundaries ──────────────
    prompt = f"""You are the Lead Curiosity & Topic Discovery Specialist for YouTube Channel: '{niche_name}'.
Your absolute mandate is to discover INCREDIBLY COOL, UNKNOWN, HIGH-INTRIGUE secrets that ordinary people DEEPLY want to know about.

CHANNEL NICHE SCOPE:
{allowed_desc}

ACTIVE TARGET SUB-CLUSTER:
"{current_subcluster}"

{topic_instruction}

STRICT CHANNEL BOUNDARY & NEGATIVE CONSTRAINTS (MANDATORY — ZERO TOLERANCE):
{strict_negatives}

THE "MIND-BLOWN" TOPIC MANDATE (ZERO GENERIC SLOP):
1. ZERO COMMON KNOWLEDGE: Absolutely reject topics taught in standard school textbooks or widely known internet trivia (e.g. "honey never spoils", "sharks don't sleep", "whales are big", "how bridges are built"). The topic MUST reveal something that 99% of educated adults do NOT know.
2. THE PHYSICAL PARADOX: The best topics pit two seemingly impossible physical realities against each other:
   - "The organism that snaps its own bones to use them as external claws"
   - "The glass teardrop that shatters a bullet but turns to powder with a tiny scratch"
   - "The machine so precise that a 1-nanometer mirror shift halts global smartphone supply"
   - "Why airlines deliberately sell 10% more tickets than physical seats on every flight"
   - "The ancient sword alloy that modern supercomputers still cannot replicate"
3. CONCRETE NAMED ANCHOR: Always name the exact real-world organism (with common or binomial name), specific machine, alloy, cartel, or event. Never use vague generalities like 'an animal' or 'scientists found a machine'.
4. INSTANT CURIOSITY TEST: Would someone scrolling TikTok or YouTube Shorts at 1 AM immediately stop and text this to a friend? If no, DISCARD IT.
5. ZERO DRY LOGISTICS: Strictly forbidden are municipal pavement reports, airport tarmac weight regulations, dry corporate filings, or generic textbook definitions.

Do NOT suggest any topic similar to these recently published topics:
{json.dumps(recent_topics, indent=2)}

Return ONLY a raw JSON array of 5 objects. No markdown, no preamble.
Each object must have exactly these fields:
- "topic": specific, punchy curiosity subject naming the real anomaly or object (15-25 words max)
- "short_hook": opening question or bold statement, 8 words or less, creates an irresistible curiosity gap
- "hook_type": one of "curiosity_gap", "contrarian", "time_pressure", "self_identification", "narrative_pull"
- "for_format": "short", "long", or "both"
- "subcluster": "{current_subcluster}"
"""

    print(f"[Phase1] Requesting topics for {niche_name} — subcluster: '{current_subcluster}' | trending: {is_trending}")
    client = GeminiClient()
    topics_list = []
    try:
        response_text = client.generate_text(prompt, use_grounding=False, temperature=0.75)
        parsed = _robust_json_loads(response_text)
        if isinstance(parsed, list) and parsed:
            topics_list = parsed
    except Exception as e:
        print(f"[Phase1] Error fetching or parsing topics from Gemini: {e}")

    # ── 4. Filter generated topics: boundary validation + deduplication ───────
    selected_topic = None
    for item in topics_list:
        if not isinstance(item, dict):
            continue
        if item.get("for_format", "both") not in (format_type, "both"):
            continue
        topic_title = item.get("topic", "").strip()
        is_valid, reason = validate_topic_boundary(topic_title, boundary)
        if not is_valid:
            print(f"[Phase1 Boundary Filter] Dropping off-niche candidate '{topic_title}': {reason}")
            continue
        if is_duplicate(topic_title, published):
            continue
        selected_topic = item
        break

    # Retry loop if all candidate topics were off-niche or duplicates
    attempts = 0
    while not selected_topic and attempts < 2:
        attempts += 1
        print(f"[Phase1] Retrying topic generation with stricter boundary enforcement (Attempt {attempts}/2)...")
        retry_prompt = prompt + "\nCRITICAL: The previous candidates were rejected for being off-niche or duplicates. Stay 100% strictly within " + current_subcluster
        try:
            response_text = client.generate_text(retry_prompt, use_grounding=False, temperature=0.75 + (attempts * 0.05))
            new_list = _robust_json_loads(response_text)
            if isinstance(new_list, list):
                for item in new_list:
                    if not isinstance(item, dict):
                        continue
                    if item.get("for_format", "both") not in (format_type, "both"):
                        continue
                    topic_title = item.get("topic", "").strip()
                    is_valid, reason = validate_topic_boundary(topic_title, boundary)
                    if not is_valid:
                        print(f"[Phase1 Boundary Filter] Dropping off-niche candidate '{topic_title}': {reason}")
                        continue
                    if is_duplicate(topic_title, published):
                        continue
                    selected_topic = item
                    break
        except Exception as e:
            print(f"[Phase1] Error during retry topic generation: {e}")

    # ── 5. Rich fallback pool if Gemini failed or produced off-niche output ───
    if not selected_topic:
        print(f"[Phase1] Using verified non-duplicate topic from {niche_name} RICH_FALLBACK_TOPICS pool...")
        selected_topic, next_fallback_idx = get_next_fallback_topic(
            format_type=format_type,
            current_subcluster=current_subcluster,
            published=published,
            start_idx=fallback_idx
        )
        fallback_idx = next_fallback_idx
    else:
        fallback_idx = (fallback_idx + 1) % len(RICH_FALLBACK_TOPICS)

    print(f"[Phase1] Final Selected Topic: {selected_topic['topic']}")

    # ── 6. Persist state ──────────────────────────────────────────────────────
    published.append(selected_topic["topic"])
    published = published[-TOPIC_LOG_SIZE:]
    next_subcluster_idx = (subcluster_idx + 1) % len(CHANNEL_SUBCLUSTERS)

    with open(topic_log_path, "w", encoding="utf-8") as f:
        json.dump({
            "topics": published,
            "subcluster_idx": next_subcluster_idx,
            "fallback_idx": fallback_idx,
            "call_count": call_count
        }, f, indent=2)

    return selected_topic
