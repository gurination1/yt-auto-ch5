import os
import json
from pipeline.config import TOPIC_LOG_SIZE, ENGINEERING_SUBCLUSTERS
from pipeline.gemini import GeminiClient, _robust_json_loads

def select_topic(format_type: str) -> dict:
    # ── 1. Load published topics log ─────────────────────────────────────────
    topic_log_path = "published_topics.json"
    if os.path.exists(topic_log_path):
        try:
            with open(topic_log_path, "r") as f:
                data = json.load(f)
                published = data.get("topics", [])
                subcluster_idx = data.get("subcluster_idx", 0)
                call_count = data.get("call_count", 0)
        except Exception as e:
            print(f"Warning: Failed to load published topics: {e}")
            published = []; subcluster_idx = 0; call_count = 0
    else:
        published = []; subcluster_idx = 0; call_count = 0

    recent_topics = published[-TOPIC_LOG_SIZE:]
    call_count += 1

    # ── 2. Determine subcluster + evergreen vs trending ──────────────────────
    current_subcluster = ENGINEERING_SUBCLUSTERS[subcluster_idx % len(ENGINEERING_SUBCLUSTERS)]
    is_trending = (call_count % 3 != 0)   # 2 out of 3 calls = trending topic

    if is_trending:
        topic_instruction = (
            f"Use Google Search to find mind-blowing, highly viral recent discoveries or breakthroughs from the last 24-48 hours specifically about {current_subcluster}. "
            f"Generate 5 TRENDING topics that reveal a startling reality normal people did NOT know. "
            f"STRICT RULES: Must be a concrete, verified true discovery with massive visual curiosity. NO dry academic papers. "
            f"Every topic must make an average person say: 'Wait, is that actually real?!'"
        )
    else:
        topic_instruction = (
            f"Generate 5 insanely fascinating, real-world EVERGREEN topics about {current_subcluster}. "
            f"CRITICAL REQUIREMENTS: "
            f"1. Must reveal a bizarre, shocking, or counter-intuitive secret that 99% of people do NOT know. "
            f"2. FORBIDDEN: Do NOT write generic textbook concepts (e.g. 'Quantum Computing Superposition Logic', 'How Photosynthesis Works', 'What if giant excavators dig canals'). "
            f"3. REQUIRED: A specific real-world anomaly, unbelievable physical fact, or mind-bending paradox (e.g. 'The metal that melts in your hand but shatters glass', 'Why hot water freezes faster than cold water', 'The room that is so quiet you can hear your own blood pumping'). "
            f"4. Easy to understand: An 8th grader must instantly grasp why it is insane. Zero PhD jargon."
        )

    # ── 3. Build Gemini prompt ───────────────────────────────────────────────
    prompt = f"""{topic_instruction}

Sub-cluster focus for this batch: {current_subcluster}

CRITICAL: Do NOT suggest any topic similar to these recently published topics:
{json.dumps(recent_topics, indent=2)}

SAFETY & COMPLIANCE CONSTRAINTS (MANDATORY):
- The topics MUST be 100% advertiser-friendly, family-friendly, and compliant with YouTube/Meta community guidelines.
- Strictly AVOID: medical advice, health/cure claims, Covid-19/vaccine/epidemic speculation, dangerous stunts/activities, illegal substances, or weapons.
- Avoid political controversies, conspiracy theories, or tragic/graphic events.
- Focus on educational, curious, and inspiring megastructures, colossal machinery, and engineering marvels.

AUDIENCE & HOOK RULES:
- The topic MUST be so clear, punchy, and intriguing that someone scrolling TikTok or Shorts immediately stops.
- Pick concrete gigantic machines, subsea tunnels, colossal bridges, or engineering feats with high visual payoff.
- FORBIDDEN: Abstract theories, philosophical musings, hypothetical scenarios ('What if X happened...').

Return ONLY a raw JSON array of objects. No markdown, no preamble.
Each object must have exactly these fields:
- "topic": specific, punchy curiosity subject naming the real anomaly or object (e.g. "The Bagger 293: The 14,000-ton colossal excavator that holds the world record for land vehicles")
- "short_hook": opening question or bold statement, 8 words or less, creates an irresistible curiosity gap
- "hook_type": one of "curiosity_gap", "contrarian", "time_pressure", "self_identification", "narrative_pull"
- "for_format": "short", "long", or "both"
- "subcluster": the sub-cluster this belongs to (string)
"""

    print(f"[Phase1] Requesting topics — subcluster: {current_subcluster} | trending: {is_trending}")
    client = GeminiClient()
    try:
        response_text = client.generate_text(prompt, use_grounding=False, temperature=0.85)
        topics_list = _robust_json_loads(response_text)
        if not isinstance(topics_list, list):
            raise ValueError("Response is not a JSON list")
        if not topics_list:
            raise ValueError("Response is an empty list")
    except Exception as e:
        print(f"[Phase1] Error fetching or parsing topics from Gemini: {e}")
        import random, time
        rand_id = int(time.time()) % 1000
        topics_list = [
            {"topic": "The Bagger 293: The 14,000-ton colossal excavator that holds the world record for land vehicles", "short_hook": "This machine is heavier than 30 Boeing 747s!", "hook_type": "curiosity_gap", "for_format": "both", "subcluster": current_subcluster},
            {"topic": "The Gotthard Base Tunnel: How engineers bored a 57-kilometer train tunnel beneath the Alps", "short_hook": "How did engineers drill 57 kilometers under mountains?", "hook_type": "curiosity_gap", "for_format": "both", "subcluster": current_subcluster},
            {"topic": "The Taipei 101 Tuned Mass Damper: The 660-ton golden pendulum that saves the skyscraper from typhoons", "short_hook": "A 660-ton golden ball saves this skyscraper.", "hook_type": "curiosity_gap", "for_format": "both", "subcluster": current_subcluster},
            {"topic": "The Akashi Kaikyo Bridge: The 4-kilometer suspension bridge that survived a 7.2 magnitude earthquake mid-construction", "short_hook": "This bridge survived a massive earthquake mid-construction.", "hook_type": "curiosity_gap", "for_format": "both", "subcluster": current_subcluster}
        ]

    # ── 4. Pick first topic matching format_type and not a duplicate ─────────
    import re
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

    def is_duplicate(new_topic: str) -> bool:
        new_keys = get_keywords(new_topic)
        if not new_keys:
            return False
        for old_topic in published:
            old_keys = get_keywords(old_topic)
            overlap = new_keys.intersection(old_keys)
            if len(overlap) >= 3 or (len(new_keys) > 0 and len(overlap) / len(new_keys) >= 0.5):
                print(f"[Similarity Check] Rejecting topic '{new_topic}' due to overlap {overlap} with: '{old_topic}'")
                return True
        return False

    selected_topic = None
    for item in topics_list:
        if item.get("for_format", "both") in (format_type, "both"):
            if not is_duplicate(item.get("topic", "")):
                selected_topic = item
                break
    if not selected_topic and topics_list:
        selected_topic = topics_list[0]

    # Retry loop if all candidate topics were duplicates
    attempts = 0
    while not selected_topic and attempts < 3:
        attempts += 1
        print(f"[Phase1] All generated topics were duplicates. Retrying topic generation (Attempt {attempts}/3)...")
        response_text = client.generate_text(prompt, use_grounding=is_trending, temperature=0.75 + (attempts * 0.05))
        try:
            topics_list = _robust_json_loads(response_text)
            if isinstance(topics_list, list) and topics_list:
                for item in topics_list:
                    if item.get("for_format", "both") in (format_type, "both"):
                        if not is_duplicate(item.get("topic", "")):
                            selected_topic = item
                            break
        except Exception as e:
            print(f"Error parsing retried topics: {e}")

    # Fallback to first generated if no non-duplicate found
    if not selected_topic:
        print("[Phase1] Warning: Could not generate a completely non-duplicate topic. Using first available as fallback.")
        for item in topics_list:
            if item.get("for_format", "both") in (format_type, "both"):
                selected_topic = item
                break
        if not selected_topic:
            selected_topic = topics_list[0]
            selected_topic["for_format"] = format_type


    print(f"[Phase1] Selected: {selected_topic['topic']}")

    # ── 5. Persist state ──────────────────────────────────────────────────────
    published.append(selected_topic["topic"])
    published = published[-TOPIC_LOG_SIZE:]
    next_subcluster_idx = (subcluster_idx + 1) % len(ENGINEERING_SUBCLUSTERS)

    with open(topic_log_path, "w") as f:
        json.dump({
            "topics": published,
            "subcluster_idx": next_subcluster_idx,
            "call_count": call_count
        }, f, indent=2)

    return selected_topic
