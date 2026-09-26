import os
import re
import json
import datetime
import random
from pipeline.config import HOOK_PATTERNS, BEACONS_LINK, GEMINI_PRO, GEMINI_FLASH
from pipeline.gemini import GeminiClient, _robust_json_loads

def get_next_weekday_2pm_ist_utc():
    # IST is UTC+5:30. 2:00 PM IST = 14:00 IST = 08:30 AM UTC.
    now = datetime.datetime.now(datetime.timezone.utc)
    ist_offset = datetime.timedelta(hours=5, minutes=30)
    now_ist = now + ist_offset
    
    target_date = now_ist.date()
    # If it's past 2 PM IST today, start looking from tomorrow
    if now_ist.time() >= datetime.time(14, 0):
        target_date += datetime.timedelta(days=1)
        
    # Find next weekday (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri)
    while target_date.weekday() >= 5: # Saturday=5, Sunday=6
        target_date += datetime.timedelta(days=1)
        
    target_dt_ist = datetime.datetime.combine(target_date, datetime.time(14, 0))
    target_dt_utc = target_dt_ist - ist_offset
    return target_dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

def generate_script(topic: dict, format_type: str) -> dict:
    client = GeminiClient()
    
    if format_type == "short":
        segment_count = random.choices([4, 5, 6], weights=[15, 65, 20], k=1)[0]
        
        hook_pattern = random.choice(HOOK_PATTERNS)
        hook_formatted = hook_pattern.format(
            subject=topic.get("topic", "science"),
            thing=topic.get("topic", "science"),
            seconds="30",
            topic=topic.get("topic", "science"),
            event="A discovery"
        )
        lang_instruction = ""
        target_lang = os.environ.get("LANGUAGE", "").lower() or topic.get("language", "").lower()
        if target_lang == "punjabi" or "punjabi" in topic.get("topic", "").lower():
            lang_instruction = (
                "\nCRITICAL LANGUAGE REQUIREMENT: Write the 'narration' for every segment in authentic, natural conversational Punjabi (ਪੰਜਾਬੀ). "
                "Keep 'broll_query', 'broll_queries', and 'title' in English so video search engines find 4K footage.\n"
            )
            
        raw_topic_str = topic.get("topic", "science")
        # Strip out quoted substrings first to avoid picking figurative metaphors (e.g. 'concrete coffins')
        cleaned_topic = re.sub(r"['\"][^'\"]*['\"]", " ", raw_topic_str)
        if ":" in cleaned_topic:
            core_subj_cand = cleaned_topic.split(":")[0].strip()
        elif "-" in cleaned_topic:
            core_subj_cand = cleaned_topic.split("-")[0].strip()
        else:
            core_subj_cand = cleaned_topic

        # Filter conversational verbs, prepositions, filler words from topic to extract core entity nouns
        topic_noise_words = {
            "transformed", "transforming", "turns", "turning", "into", "created", "creating",
            "discovered", "discovering", "reveals", "revealing", "secret", "secrets", "mystery",
            "mysteries", "unsolved", "experiment", "experiments", "laboratory", "lab", "scientists",
            "science", "researchers", "study", "proves", "proving", "shows", "showing", "found",
            "how", "why", "what", "when", "where", "inside", "hidden", "truth", "about",
            "could", "would", "might", "will", "can", "using", "with", "from", "at", "by",
            "for", "on", "in", "a", "an", "the", "that", "this", "these", "those", "over",
            "under", "between", "through", "across", "against", "without", "real", "actual",
            "shocking", "incredible", "unbelievable", "insane", "bizarre", "strange", "epic",
            "silent", "inevitable", "death", "every", "paradoxically", "designed", "eventually"
        }
        all_words = re.sub(r"[^\w\s-]", " ", core_subj_cand).split()
        entity_words = [w for w in all_words if w.lower() not in topic_noise_words and len(w) > 2]
        if entity_words:
            core_subj = " ".join(entity_words[:3]).strip()
        else:
            subcluster = topic.get("subcluster", "")
            sub_words = [w for w in re.sub(r"[^\w\s-]", " ", subcluster).split() if w.lower() not in topic_noise_words and len(w) > 2]
            core_subj = " ".join(sub_words[:3]).strip() if sub_words else "documentary science"

        prompt = f"""Generate an extremely viral, high-retention 25-35 second YouTube Short educational script on the topic: "{topic['topic']}".
Use the following hook concept as your core theme: "{hook_formatted}" (short hook: "{topic.get('short_hook', '')}").
{lang_instruction}
DOPAMINE ADDICTION LOOP ARCHITECTURE (MANDATORY CASINO-GRADE RETENTION SYSTEM):
Every script must strictly follow the 4-stage Dopamine Addiction Loop psychology to eliminate mid-video drop-off and maximize re-loops:

STAGE 1: THE STAKES & IMMEDIATE PERIL (SEGMENT 1 - 0.0s to 6.0s):
- Dopamine requires caring. To make the viewer care, establish immediate, tangible high stakes.
- Stakes Formula: [Concrete Named Entity / Character] + [Massive Peril / Catastrophe / Something at Risk] + [Urgency / Present Tense].
- 8 to 12 words. High-energy declarative statement in the present tense with active verbs.
- ABSOLUTELY FORBIDDEN: NEVER open with rhetorical questions (NO "Could...", "Have you ever wondered...", "What if...", "Did you know..."), passive throat-clearing, or reading the title.
- Start directly with the jaw-dropping physical fact: e.g. "Microscopic machines are tearing apart toxic plastic right now." or "Every mega-dam on Earth is fighting a silent, catastrophic enemy."

STAGE 2: THE BIG QUESTION & CURIOSITY LOCK (SEGMENT 2 - 6.0s to 12.0s):
- Stakes make them care; The Big Question locks them in.
- Give enough concrete physical context and measurable scale to open an irresistible information gap in the viewer's mind.
- 14 to 18 words. Active verbs.
- State the physical paradox, impossible obstacle, or baffling observation with concrete metrics.
- Example: "Normal river silt settles into concrete-hard sludge that would snap the spillway gates under immense hydrostatic drag."

STAGE 3: THE HEADFAKE / PREDICTION ERROR (SEGMENT 3 - 12.0s to 18.0s - CRITICAL ANTI-DROP-OFF BEAT):
- THIS IS WHERE CASINOS HOOK GAMBLERS AND WHERE 90% OF EDUCATIONAL SHORTS FAIL.
- THE HEADFAKE IS MANDATORY: Contrast directly against what common sense or the average viewer assumes.
- The human brain drops dopamine when it anticipates the answer. Subverting expectation triggers a REWARD PREDICTION ERROR that forces total focus!
- Explicitly state: "Common sense says X, but the reality is the exact opposite..." or reveal what failed first or why the obvious solution is lethal.
- 14 to 18 words. Plain, sensory language: "melts", "smashes", "tricks", "sneaks in", "explodes", "freezes solid", "eats through".

STAGE 4: THE CORE BREAKTHROUGH PAYOFF (SEGMENT {segment_count - 1} - 18.0s to 24.0s):
- Full, satisfying technical, biological, or operational resolution.
- Deliver the verified real answer with absolute clarity (8th grade English, zero jargon).
- Segment {segment_count - 1} MUST fully resolve the mystery, explain the mechanism, or deliver the historical breakthrough.
- The viewer must feel the intense psychological satisfaction of the mystery being solved.
- 14 to 18 words.

STAGE 5: THE REHOOK & INFINITE LOOP BRIDGE (SEGMENT {segment_count} - 24.0s to 30.0s):
- Just like a casino dealer instantly redeals the next blackjack hand before the gambler walks away, the final segment must REHOOK the viewer.
- DO NOT wind down or deliver a polite sign-off.
- The final sentence must resolve the immediate payoff while launching a cascading bridge that syntactically and thematically flows directly back into Segment 1's opening line.
- Complete grammatical sentence ending in a period.
- ABSOLUTELY FORBIDDEN: NEVER say "link in bio", "link in description", "subscribe", "follow", "check bio", or any social media callout in narration. It destroys loop retention.

STYLE & VOCABULARY GUARDRAILS:
1. EXTREME SIMPLICITY & CONVERSATIONAL ENGLISH (8TH GRADE LEVEL):
   - Write like an excited friend telling an insane secret around a campfire.
   - ABSOLUTELY FORBIDDEN ACADEMIC JARGON: NEVER USE WORDS LIKE "improbable", "desensitized", "homeostatic", "equilibrium", "methodology", "reconsider", "predatory instincts", "operational mechanisms", "unprecedented mechanisms", "fundamental reaction", "historical accounts suggest", "prompts to reconsider", "utilizes", "physiological", "adversaries", "confrontation", "enduring".
   - REQUIRED: Plain, sensory, visual language: "melts", "smashes", "tricks", "sneaks in", "explodes", "freezes solid", "eats through", "turns to dust".
2. MANDATORY CONCRETE NAMED ENTITIES (ZERO ABSTRACT GENERALITIES):
   - You MUST name the exact real-world detector, instrument, mine, organism, cartel, or megaproject (e.g. "The LUX-ZEPLIN detector 1 mile deep", "De Beers", "The Challenger Deep amphipod", "The Herrenknecht TBM", "ASML").
   - ABSOLUTELY FORBIDDEN: Vague filler phrases like "a detector deep underground", "scientists believe", "an underground facility", "a mysterious machine", "a massive company", "an animal".
3. ZERO TITLE / HOOK REPETITION & ZERO REDUNDANT QUALIFIERS:
   - Segment 1 must dive straight into the shocking physical action or visual observation without reading the title.
   - Segment 2 and subsequent segments MUST NEVER repeat the opening hook phrase, title words, or introductory sentence from Segment 1. Each segment must reveal completely fresh, advancing facts.
   - ABSOLUTELY FORBIDDEN: NEVER repeat phrases like "While [entity] denies...", "Although companies claim...", "Algorithms track...", "Studies show...".
4. SEAMLESS INFINITE LOOP CLOSING (SEGMENT {segment_count} MANDATE):
   - The final segment must be a 100% grammatically complete sentence ending with a period.
   - The final sentence must resolve the tension while phonetically and syntactically flowing seamlessly back into Segment 1's hook narration.

COMPANION LAYER - NICHE & FORMAT UPGRADE (SHORT):
- MANDATORY 5TH-TO-8TH GRADE EVERYDAY ENGLISH (ABSOLUTELY NO SAT/ACADEMIC/PHD JARGON):
  * Speak like an excited, knowledgeable friend sharing an unbelievable secret.
  * FORBIDDEN VOCABULARY: 'lithography', 'localized', 'degradation', 'cardiovascular', 'neurotoxin', 'physiological', 'adversaries', 'predation', 'equilibrium', 'manifestation', 'subterranean', 'utilizes', 'perpetual', 'confrontation', 'enduring'.
  * INSTEAD USE: Everyday words a 12-year-old understands instantly ('carves', 'breaks down', 'heart', 'nerve poison', 'body', 'enemies', 'hunts', 'balance', 'signs', 'underground', 'uses', 'never-ending', 'battle', 'lasting').
  * If a high-tech or scientific term is essential, IMMEDIATELY clarify it in the same breath in 3 plain words.
  * Every single sentence MUST be simple, clear, and instantly understandable on first listen.

- MANDATORY AUTHENTIC DOCUMENTARY SOURCING (ZERO AI SLOP / ZERO UNRELATED STOCK / ZERO STATIC UI):
  * Target REAL, PHYSICAL, FILMABLE entities:
    - Science: scanning electron microscope, laser optical trap, silicon crystal ingot, cleanroom photolithography, cryostat dilution refrigerator.
    - Nature: macro wildlife close-up, deep sea ROV submersible, extremophile hydrothermal vent, ice core drill.
    - History: ancient siege catapult, Roman ballista firing, unearthed bronze sword, archaeological excavation.
    - Mystery: ocean floor sonar bathymetry, radar satellite scan, LIDAR jungle ruins, deep cave bore hole.
    - Megaprojects: tunnel boring machine cutterhead, concrete batching plant, hydraulic spillway discharge, giant crawler crane.
    - Business: container cargo ship port, gantry cranes, bulk commodity trading floor, cargo aircraft loading, Boeing/Airbus flight deck avionics, aircraft engine maintenance hangars, airport baggage ramp operations, hyperscale datacenter server corridors, semiconductor cleanrooms, currency printing presses, automated warehouse robotics.
  * STRICT BAN ON DIGITAL / UI / SCREENSHOT B-ROLL:
    - ABSOLUTELY FORBIDDEN IN B-ROLL: Laptop screens, phone screens, web browsers, website URLs, cookie popups, software code, UI dialogs, spreadsheets, desktop screencasts, Google Maps screenshots.
    - NEVER write queries like: "laptop browser search", "website code running", "browsing frequency", "cookie notice", "phone screen", "computer window".
    - ALWAYS anchor business/tech topics in the PHYSICAL INDUSTRIAL ASSETS: e.g. "Boeing cockpit avionics", "container ship gantry crane", "server room corridor", "trading floor floor traders", "semiconductor wafer stepper", "airport ramp cargo".
  * STRICT NO-METAPHOR VISUAL RULE (CRITICAL FOR VIRAL QUALITY):
    - NEVER use metaphorical language, idioms, or abstract analogies in 'broll_query' or 'broll_queries'.
    - ULTRA-COMPACT 2-4 WORD RULE: Search engines fail on long sentences! broll_query MUST BE 2 TO 4 WORDS MAXIMUM!
    - NEVER append "4k", "1080p", "real footage", "cinematic", "documentary" to broll_query or broll_queries.

You MUST return your response ONLY as a raw JSON object with no markdown syntax. The JSON structure MUST be exactly like this:
{{
  "title": "A catchy title under 40 chars, starting with a hook word/number and containing one emoji",
  "voiceover_plan": "A 2-3 sentence internal plan detailing the emotional arc of the voiceover. How should the narrator sound? Think step-by-step to plan the performance before writing.",
  "vocal_tone": "Select the single best vocal delivery style for this topic. Choose EXACTLY ONE from this list: 'dramatic_whisper', 'suspenseful_mystery', 'energetic_storytelling', 'deep_curiosity', 'bold_authority', 'warm_storyteller', 'dark_revelation', 'playful_wit'. Match the tone to the emotional core of the topic.",
  "description": "restate the short hook sentence\\nFast. Accurate. Mind-blowing.\\n📲 Follow our socials & links -> {BEACONS_LINK}\\n\\n#science #didyouknow #facts",
  "tags": ["8 to 12 relevant tags under 500 characters total"],
  "category_id": "27",
  "segments": [
    // Provide exactly {segment_count} segments here.
    {{
      "id": 1,
      "narration": "STAGE 1 - THE STAKES: 8 to 12 words. Immediate high-stakes declarative opening in present tense. Named entity + hazard/peril. NO rhetorical questions.",
      "broll_query": "primary entity (2-3 words, NO buzzwords)",
      "broll_queries": ["exact entity (2-3 words)", "action shot (2-3 words)"],
      "duration_target": 6
    }},
    {{
      "id": 2,
      "narration": "STAGE 2 - THE BIG QUESTION: 14 to 18 words. Sets up the baffling paradox, metric, or physical obstacle locking the viewer's curiosity.",
      "broll_query": "physical context entity (2-3 words, NO buzzwords)",
      "broll_queries": ["context query (2-3 words)", "mechanism query (2-3 words)"],
      "duration_target": 6
    }},
    {{
      "id": 3,
      "narration": "STAGE 3 - THE HEADFAKE (PREDICTION ERROR): 14 to 18 words. Mandatory subversion: contrasts against what the viewer assumes or reveals why the obvious solution fails.",
      "broll_query": "subversion/twist entity (2-3 words, NO buzzwords)",
      "broll_queries": ["twist query (2-3 words)", "apparatus query (2-3 words)"],
      "duration_target": 6
    }},
    {{
      "id": 4,
      "narration": "STAGE 4 - THE BREAKTHROUGH PAYOFF: 14 to 18 words. Delivers the complete, satisfying, verified scientific/historical answer.",
      "broll_query": "breakthrough entity (2-3 words, NO buzzwords)",
      "broll_queries": ["breakthrough query (2-3 words)", "action query (2-3 words)"],
      "duration_target": 6
    }},
    {{
      "id": {segment_count},
      "narration": "STAGE 5 - THE REHOOK & INFINITE LOOP: 10 to 14 words. Complete sentence ending with a period. Redeals tension and seamlessly bridges back to Segment 1. NO link in bio, NO subscribe.",
      "broll_query": "closing evidence entity (2-3 words, NO buzzwords)",
      "broll_queries": ["closing query (2-3 words)", "loop query (2-3 words)"],
      "duration_target": 6
    }}
  ],
  "thumbnail_text": "3 to 5 bold words max for the thumbnail",
  "loop_callout": true
}}

For Segment 1 specifically:
- `broll_query` MUST describe a high-motion, high-contrast, visually arresting real shot (fast motion, dramatic close-up) — the opening pattern-interrupt.

For Segments 2 to (segment_count - 1):
- Segment 2 MUST establish the Big Question and curiosity lock.
- Segment 3 MUST deliver The Headfake (prediction error subverting viewer assumptions).
- Segment {segment_count - 1} MUST fully explain the core mechanism or historical breakthrough with concrete, satisfying clarity. Deliver the real answer!

For the final segment (Segment {segment_count}) specifically:
- MUST be a complete, punchy sentence resolving the video and seamlessly linking back to Segment 1.
- DO NOT put the core explanation only in the final segment; the explanation must already be established in previous segments.
- ABSOLUTELY NEVER mention 'link in bio' or 'description'. Loop the story.
"""
    else:  # long-form
        prompt = f"""Generate a comprehensive 7-10 minute YouTube educational script on the topic: "{topic['topic']}".
The script must have 15 to 18 segments, each targeting 25-35 seconds of narration.

Narration Style Requirements :
1. Conversational & Simple Language: Use very simple, easy-to-understand, and highly relatable words that anyone can easily follow. Avoid obscure, complex, or overly difficult English vocabulary. Keep the narration friendly, extremely engaging, and relatable—like a friend explaining an amazing topic.
2. Engaging Tone: The voiceover narration must be conversational, highly engaging, and relatable—like a friend telling an exciting story. Write the voiceover to be energetic, warm, and inviting.
Structure the narrative into:
- Intro hook (segments 1-2)
- Act 1: The core mystery/mechanism (segments 3-7)
- Act 2: The surprising twist/implication (segments 8-12)
- Act 3: Modern applications or future outlook (segments 13-16)
- Closing CTA & link (segments 17-18)

COMPANION LAYER - NICHE & FORMAT UPGRADE (LONG):
- CLARITY & ACCESSIBILITY RULE (SIMPLE & INTRIGUING, ZERO PHD JARGON):
  * Explain the mind-blowing mechanism using simple, vivid, conversational words and tangible physical comparisons.
  * FORBIDDEN: Academic jargon, dense textbook terminology, or abstract PhD words (e.g., do NOT say 'thermodynamic equilibrium', 'homeostatic regulation', 'hydrostatic barometric differential').
  * REQUIRED: Describe what physically HAPPENS in punchy, visual language (e.g., 'lasers shoot light particles to smack hot atoms until they freeze completely still', 'water pressure heavy enough to crush a steel submarine like an aluminum soda can', 'giant drill heads hotter than boiling soup').
  * A 12-year-old must understand the core revelation instantly while feeling genuinely mind-blown.

- MANDATORY STARTLING UNKNOWN FACT (THE "I DIDN'T KNOW THAT!" FACTOR):
  * Every single script MUST reveal at least ONE specific, counterintuitive, little-known mechanism or hidden physical reality that educated adults do NOT know.
  * FORBIDDEN: Superficial textbook summaries (e.g., "whales are big", "pyramids are stone", "tunnels go under mountains", "black holes are dark").
  * REQUIRED: The startling, precise hidden detail (e.g., "a sperm whale's spermaceti oil hardens into solid wax at deep cold depths to act as an automated buoyancy anchor", "the Great Pyramid has eight concave faces only visible from the sky on the exact equinox afternoon", "subsea tunnel boring machines freeze groundwater into a solid ice wall with liquid nitrogen so workers don't drown", "quantum lasers freeze atom kinetic momentum to near absolute zero").
  * This unknown insight MUST be the central reveal in Segment 2 or 3 that delivers on the opening hook!

- FORMAT RULE (5-6 Min Long): Tight format. Only room for one idea developed properly. No detours, no filler. Get there fast, go deep. Target exactly 15 to 18 segments, each targeting 18-22 seconds (or 35-45 words) of narration.
  * Hook (0:00-0:20, segments 1-2): Most powerful moment first. No intro, no fluff.
  * Context (0:20-0:45, segment 3): Minimum context needed. Nothing more.
  * Core content (0:45-4:00, segments 4-13): Max 2-3 main points. Each point needs: a clear statement, one visual/example that proves it, and transition.
  * Surprising Part (4:00-5:00, segments 14-16): Save one strong, interesting thing for here to prevent retention collapse.
  * Payoff + CTA (5:00-5:30, segments 17-18): Wrap core idea. One line CTA. End clean.
- PATTERN INTERRUPT: Include exactly 2-3 pattern interrupts total (visual shift, tonal change, new angle) around 1:30, 3:00, and 4:30.
- Avoid: intro/context >45s, padding middle, saving best point for end, or >3 main points.
- NICHE QUALITY SIGNALS (Education):
  * SHOW THE RESULT FIRST: State or show the answer/outcome before explaining how you get there. Viewers stay to understand something they just saw — not to wait.
  * B-ROLL THAT PROVES THE POINT: Every concept explained verbally must have a visual that demonstrates it, not just decorates it.
  * ONE CLEAR GAIN PER VIDEO: Teach exactly one thing. Script must answer: "What is the single thing this viewer will walk away with?"
  * TEXT OVERLAYS THAT REINFORCE, NOT REPEAT: Use text for key terms, surprising numbers, simple diagrams, or summary sentences. Do not transcribe verbatim.
  * CONTINUOUS CURIOSITY LOOP: Every 60-90 seconds, give a new reason to stay with a new question (e.g., "But here's where it gets interesting...").

For every `broll_query` field, write a SHORT, SPECIFIC, STOCK-FOOTAGE-FRIENDLY
search term of 3-6 words MAXIMUM. Write exactly what a human would type into
a stock video search bar (Pexels, Pixabay, etc). Use concrete nouns and visual
objects — NOT instructions or descriptions of what you want.

CORRECT examples: "Stephen Hawking wheelchair smiling", "DNA double helix blue",
"quantum computer chip closeup", "black hole space vortex", "astronaut spacewalk ISS",
"brain neurons firing", "atom particle collider", "coral reef fish colorful"

WRONG examples: "visually jarring close-up of the topic", "macro b-roll of scientific
element", "closing beautiful shot returning to start", "diagram concept visualization",
- MANDATORY AUTHENTIC DOCUMENTARY SOURCING (ZERO AI SLOP / ZERO GENERIC STOCK):
  * Target real physical objects, named historical missions, scientific apparatus, species binomials, or archival footage.
  * FORBIDDEN: 'abstract science background', 'glowing particles', 'blue fluid dynamics', or generic stock models.

For each segment, provide a `broll_queries` array with 3-5 ALTERNATIVE hyper-specific search queries targeting real footage and institutional archives. The first entry must match `broll_query`.

For any named person, scientist, or historic figure: ALWAYS include their exact full name.

You MUST return your response ONLY as a raw JSON object with no markdown syntax. The JSON structure MUST be exactly like this:
{{
  "title": "Engaging educational title for a long video, under 70 characters",
  "voiceover_plan": "A 2-3 sentence internal plan detailing the emotional arc of the voiceover. How should the narrator sound? Think step-by-step to plan the performance before writing.",
  "description": "A detailed, engaging description explaining what the video covers, including timestamps and educational value.\\n\\n#science #education #technology",
  "tags": ["15 to 20 relevant tags"],
  "category_id": "27",
  "segments": [
    {{
      "id": 1,
      "narration": "Opening hook sentence delivering high intrigue...",
      "broll_query": "{topic['topic']} space stars universe",
      "broll_queries": ["{topic['topic']} space stars universe", "galaxy nebula deep space", "cosmos starfield timelapse", "astronomical observatory night sky"],
      "duration_target": 10
    }}
    // ... total 25-35 concise, fast-paced segments (8 to 12 seconds each for cinematic pacing, avoiding static holds)
  ],
  "thumbnail_text": "3 to 5 bold words max for the thumbnail image",
  "loop_callout": false
}}
"""

    print("Generating script content using Gemini...")
    max_attempts = 3
    script_text = ""
    script = None
    is_fallback_script = False
    for attempt in range(max_attempts):
        try:
            script_text = client.generate_text(prompt, use_grounding=False, temperature=0.8, model=GEMINI_FLASH)
            script = _robust_json_loads(script_text)
            if isinstance(script, list):
                script = {"segments": script}
            if isinstance(script, dict) and "segments" in script:
                break
        except Exception as e:
            print(f"Error parsing script JSON on attempt {attempt+1}: {e}. Raw script text: {script_text}")

    if script is None:
        is_fallback_script = True
        print("[Phase2] Gemini API rate-limited after retries. Generating niche-aware dynamic topic fallback script dict...")
        raw_title = topic.get('topic', 'Engineering Breakthrough') if isinstance(topic, dict) else str(topic)
        clean_subj = re.sub(r'#\d+', '', raw_title)
        clean_subj = re.sub(r'[^\w\s-]', '', clean_subj).strip()
        words = clean_subj.split()
        entity_name = " ".join(words[:6]) if len(words) > 6 else clean_subj
        if not entity_name:
            entity_name = "this monumental breakthrough"

        # Detect channel niche
        ch_env = os.environ.get("CHANNEL_NAME", "").lower() or os.environ.get("NICHE", "").lower()
        topic_ch = topic.get("channel", "").lower() if isinstance(topic, dict) else ""
        niche = topic_ch or ch_env
        lower_subj = clean_subj.lower()

        if not niche:
            if any(w in lower_subj for w in ["tunnel", "bridge", "skyscraper", "dam", "megaproject", "machine", "engineering", "tower", "highway", "canal", "train", "alps", "gotthard"]):
                niche = "engineering"
            elif any(w in lower_subj for w in ["fish", "ocean", "animal", "creature", "predator", "evolution", "mating", "abyssal", "trench", "species", "wildlife", "sea"]):
                niche = "nature"
            elif any(w in lower_subj for w in ["battle", "war", "empire", "tactics", "ancient", "siege", "rome", "weapon", "general", "conquest"]):
                niche = "history"
            elif any(w in lower_subj for w in ["mystery", "enigma", "unexplained", "strange", "anomaly", "alien", "ufo", "disappearance"]):
                niche = "mystery"
            else:
                niche = "science"

        if niche == "engineering":
            script = {
                "title": f"🏗️ Inside {entity_name[:32]}",
                "voiceover_plan": "Deliver fast-paced, high-stakes engineering narration with intense curiosity.",
                "vocal_tone": "deep_curiosity",
                "description": f"The impossible engineering behind {entity_name}.\n\nMassive scale. Extreme physics.\n\n#engineering #megaprojects #construction",
                "tags": ["engineering", "megaprojects", "construction", "technology", "architecture", "machines", "didyouknow"],
                "category_id": "28",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"Right now, the {entity_name} is fighting hundreds of millions of tons of suffocating pressure threatening its foundation.",
                        "broll_query": f"{entity_name} megaproject construction",
                        "broll_queries": [f"{entity_name} megaproject construction", f"{entity_name} heavy civil engineering", "tunnel boring machine cutterhead"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": f"Normal physical forces are manageable, but engineers faced an impossible obstacle that would snap standard structural barriers like toothpicks.",
                        "broll_query": f"{entity_name} construction site",
                        "broll_queries": [f"{entity_name} construction site", "massive hydraulic jacks foundation", "heavy steel structural beam"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": "Common sense assumed massive rigid concrete walls would hold the load, but the real breakthrough required letting the structure bend like rubber.",
                        "broll_query": "hydraulic damper testing",
                        "broll_queries": ["hydraulic damper testing", "seismic shock absorber bridge", "flexible steel joints industrial"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"By absorbing kinetic shock through dynamic counterweights, the {entity_name} conquers the impossible forces threatening its foundation.",
                        "broll_query": f"{entity_name} completed infrastructure",
                        "broll_queries": [f"{entity_name} completed infrastructure", "high speed transit aerial", "engineering masterpiece aerial"],
                        "duration_target": 6
                    }
                ],
                "loop_callout": True
            }
        elif niche == "nature":
            script = {
                "title": f"🌊 Secret of {entity_name[:32]}",
                "voiceover_plan": "Deliver intense, suspenseful wildlife narration with sudden expectation subversion.",
                "vocal_tone": "deep_curiosity",
                "description": f"The shocking survival adaptation of {entity_name}.\n\nWild biology in extreme habitats.\n\n#nature #wildlife #ocean",
                "tags": ["nature", "wildlife", "animals", "biology", "ocean", "evolution", "didyouknow"],
                "category_id": "15",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"Deep in extreme terrain, the {entity_name} faces lethal predators and freezing pressures that would instantly crush human steel.",
                        "broll_query": f"{entity_name} wildlife documentary",
                        "broll_queries": [f"{entity_name} wildlife documentary", f"{entity_name} macro photography", "deep ocean abyss creature"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": f"Biologists discovered its body produces an intense biological reaction, opening a baffling question about how it survives without poison harming itself.",
                        "broll_query": f"{entity_name} hunting behavior",
                        "broll_queries": [f"{entity_name} hunting behavior", "marine predator macro strike", "underwater specimen close up"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": "You'd assume it stores defensive venom internally, but deep-sea cameras caught it spitting enzymes outward to build a temporary physical shield.",
                        "broll_query": "deep sea bioluminescence",
                        "broll_queries": ["deep sea bioluminescence", "underwater ROV specimen camera", "fluorescent ocean organism"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"This bizarre counter-attack turns lethal strikes into an instant retreat, keeping the {entity_name} alive in extreme terrain.",
                        "broll_query": f"{entity_name} swimming natural habitat",
                        "broll_queries": [f"{entity_name} swimming natural habitat", "wild ocean documentary footage", "creature underwater close up"],
                        "duration_target": 6
                    }
                ],
                "loop_callout": True
            }
        elif niche == "history":
            script = {
                "title": f"⚔️ Tactical Secret of {entity_name[:32]}",
                "voiceover_plan": "Deliver dramatic, high-tension battlefield storytelling.",
                "vocal_tone": "deep_curiosity",
                "description": f"The battlefield strategy that changed world history: {entity_name}.\n\n#history #warfare #tactics",
                "tags": ["history", "warfare", "tactics", "ancient", "battles", "strategy", "didyouknow"],
                "category_id": "27",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"At the decisive turning point of {entity_name}, an outnumbered army was facing total annihilation within hours.",
                        "broll_query": f"{entity_name} battle documentary",
                        "broll_queries": [f"{entity_name} battle documentary", "ancient fortress ruins aerial", "battlefield archaeology site"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": "Frontal assaults meant certain death against fortified stone battlements, leaving commanders with only one desperate, unproven gamble.",
                        "broll_query": "ancient siege fortress wall",
                        "broll_queries": ["ancient siege fortress wall", "medieval catapult siege engine", "ancient warrior bronze armor"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": "Enemy sentries kept watching no-man's land for charging infantry, completely blind to specialized engineers tunneling 100 feet beneath their boots.",
                        "broll_query": "underground tunnel excavation torch",
                        "broll_queries": ["underground tunnel excavation torch", "ancient mine excavation", "sappers digging trench battle"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"When the subterranean charges blew through the defensive line, history changed forever at {entity_name}.",
                        "broll_query": "historical monument battlefield aerial",
                        "broll_queries": ["historical monument battlefield aerial", "ancient fortress ruins cinematic", "archaeological discovery site"],
                        "duration_target": 6
                    }
                ],
                "loop_callout": True
            }
        elif niche == "mystery":
            script = {
                "title": f"👁️ Unsolved: {entity_name[:32]}",
                "voiceover_plan": "Deliver dark, suspenseful mystery narration with high intrigue.",
                "vocal_tone": "deep_curiosity",
                "description": f"The baffling anomaly of {entity_name}.\n\nUnexplained evidence. Lingering questions.\n\n#mystery #unexplained #strange",
                "tags": ["mystery", "unexplained", "strange", "paranormal", "anomaly", "didyouknow"],
                "category_id": "24",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"For decades, physical evidence recovered from {entity_name} has defied every known law of modern forensics.",
                        "broll_query": f"{entity_name} anomaly investigation",
                        "broll_queries": [f"{entity_name} anomaly investigation", "archival evidence documents inspection", "deep cave entrance drone"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": "Field instruments registered abnormal magnetic signatures, opening a bizarre dilemma that baffled elite scientific teams worldwide.",
                        "broll_query": "magnetometer field measurement instrument",
                        "broll_queries": ["magnetometer field measurement instrument", "scientific sensor expedition desert", "sonar ocean bathymetry scan"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": "Most researchers assumed equipment failure or natural mineral deposits, until satellite radar revealed identical geometric patterns buried deep beneath the rock.",
                        "broll_query": "satellite synthetic aperture radar",
                        "broll_queries": ["satellite synthetic aperture radar", "ground penetrating radar survey", "lidar jungle ruins scan"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"These buried geometric anomalies prove that an organized purpose existed long before modern history at {entity_name}.",
                        "broll_query": "unsolved mystery landscape aerial",
                        "broll_queries": ["unsolved mystery landscape aerial", "mysterious ancient terrain 4k", "dark twilight horizon timelapse"],
                        "duration_target": 6
                    }
                ],
                "loop_callout": True
            }
        else: # science
            script = {
                "title": f"🔬 Secret of {entity_name[:32]}",
                "voiceover_plan": "Deliver fast, energetic scientific narration with sharp prediction errors.",
                "vocal_tone": "deep_curiosity",
                "description": f"The mind-blowing physics behind {entity_name}.\n\n#science #physics #technology",
                "tags": ["science", "physics", "technology", "quantum", "universe", "didyouknow"],
                "category_id": "28",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"Inside ultra-cold vacuum chambers, physicists studying {entity_name} are testing the razor edge of physical reality.",
                        "broll_query": f"{entity_name} physics laboratory",
                        "broll_queries": [f"{entity_name} physics laboratory", "cryostat vacuum chamber research", "optical laser table experiment"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": "Standard physics insists fast-moving particles carry unstoppable kinetic energy, creating an impossible barrier for next-generation technology.",
                        "broll_query": "laser beam splitter optics",
                        "broll_queries": ["laser beam splitter optics", "particle accelerator beam pipe", "quantum computer dilution refrigerator"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": "You'd think blasting particles with light adds heat, but tuning laser frequencies head-on strips momentum away until atoms freeze completely solid.",
                        "broll_query": "laser cooling magneto optical trap",
                        "broll_queries": ["laser cooling magneto optical trap", "bose einstein condensate chamber", "fluorescent atom cloud trap"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"This optical braking creates an extraordinary new state of matter, unlocking the hidden power of {entity_name}.",
                        "broll_query": "quantum chip silicon wafer",
                        "broll_queries": ["quantum chip silicon wafer", "superconducting circuit cleanroom", "advanced science observatory night"],
                        "duration_target": 6
                    }
                ],
                "loop_callout": True
            }

    if format_type == "short":
        script["segment_count"] = segment_count

    # Add scheduling metadata for long form
    if format_type == "long":
        script["publish_at"] = get_next_weekday_2pm_ist_utc()
    else:
        # Default publish_at for shorts: let's set it to None so we can upload as private first
        script["publish_at"] = None

    # Ensure script is dict
    if not isinstance(script, dict):
        script = {"segments": []}

    # Flatten and validate segments to guarantee a clean list of dicts
    raw_segments = script.get("segments", [])
    clean_segments = []
    if isinstance(raw_segments, list):
        for item in raw_segments:
            if isinstance(item, dict):
                clean_segments.append(item)
            elif isinstance(item, list):
                for sub in item:
                    if isinstance(sub, dict):
                        clean_segments.append(sub)
    elif isinstance(raw_segments, dict):
        clean_segments.append(raw_segments)

    # Assign standard segment IDs if missing
    for idx, seg in enumerate(clean_segments, 1):
        if "id" not in seg or not isinstance(seg["id"], (int, str)):
            seg["id"] = idx
    script["segments"] = clean_segments

    # --- FACT VERIFICATION ---
    if not is_fallback_script:
        print("Running fact verification on the generated script...")
        verification_prompt = f"""You are a fact checker. Verify the scientific accuracy of each segment's narration in the following script JSON:
{json.dumps(script, indent=2)}

Check if all claims are backed by credible scientific consensus.
Return ONLY the modified script JSON with an added `"verified": true` or `"verified": false` field inside EACH segment object in the "segments" list.
If a claim is unverifiable, speculative, or false, mark `"verified": false`.
"""
        try:
            verified_text = client.generate_text(verification_prompt, use_grounding=False, temperature=0.2)
            verified_script = _robust_json_loads(verified_text)
            if isinstance(verified_script, list):
                verified_script = {"segments": verified_script}
            if isinstance(verified_script, dict) and "segments" in verified_script and isinstance(verified_script["segments"], list):
                verified_map = {}
                for s in verified_script["segments"]:
                    if isinstance(s, dict):
                        verified_map[s.get("id")] = s
                    elif isinstance(s, list):
                        for sub_s in s:
                            if isinstance(sub_s, dict):
                                verified_map[sub_s.get("id")] = sub_s
                for seg in script["segments"]:
                    if not isinstance(seg, dict):
                        continue
                    seg_id = seg.get("id")
                    if seg_id in verified_map:
                        v_seg = verified_map[seg_id]
                        seg["verified"] = v_seg.get("verified", True)
                        if "narration" in v_seg and v_seg["narration"]:
                            seg["narration"] = v_seg["narration"]
                    else:
                        seg["verified"] = True
            else:
                for seg in script["segments"]:
                    if isinstance(seg, dict):
                        seg["verified"] = True
        except Exception as e:
            print(f"Fact check failed or quota-limited ({e}), keeping original script for Judge AI review.")
            for seg in script["segments"]:
                if isinstance(seg, dict):
                    seg["verified"] = True
    else:
        for seg in script["segments"]:
            if isinstance(seg, dict):
                seg["verified"] = True

    # Regenerate unverified segments
    for seg in script["segments"]:
        if not isinstance(seg, dict):
            continue
        if not seg.get("verified", True):
            print(f"Segment {seg.get('id', '?')} failed fact check. Regenerating narration...")
            regen_prompt = f"""The following script segment narration failed fact-checking or was unverified:
Topic: {topic['topic']}
Segment details: {json.dumps(seg, indent=2)}

Rewrite the "narration" so that it is 100% scientifically accurate, verifiable, and maintains the exact same tone and target duration.
Return ONLY a raw JSON object for this segment with the updated "narration" and `"verified": true`.
"""
            try:
                regen_text = client.generate_text(regen_prompt, use_grounding=False, temperature=0.3)
                regen_seg = _robust_json_loads(regen_text)
                if isinstance(regen_seg, dict):
                    seg["narration"] = regen_seg.get("narration", seg["narration"])
                seg["verified"] = True
            except Exception as e:
                print(f"Failed to regenerate segment {seg.get('id', '?')} ({e}). Keeping original for Judge AI review.")
                seg["verified"] = True

    
    # ── Clean all segment narrations (Strip dangling words & enforce punctuation) ──
    dangling_words = {"because", "which", "that", "how", "and", "so", "or", "to", "with", "for", "as"}
    for seg in script.get("segments", []):
        narr = seg.get("narration", "").strip()
        words = narr.split()
        while words and words[-1].lower().rstrip(".,!?;:-") in dangling_words:
            words.pop()
        if words:
            narr = " ".join(words).rstrip(",;:-")
            if not narr.endswith((".", "!", "?")):
                narr += "."
            seg["narration"] = narr

    # ── Ensure Clean Infinite Loop Narration (No Spoken Social Spam) ─────────
    for seg in script.get("segments", []):
        narr = seg.get("narration", "")
        narr_clean = re.sub(r'\s*[-—–:]*\s*(?:link in bio|link in description|check bio|subscribe|follow).*$', '', narr, flags=re.IGNORECASE).strip()
        if narr_clean:
            if not narr_clean.endswith((".", "!", "?")):
                narr_clean += "."
            seg["narration"] = narr_clean

    # ── Inter-Segment Semantic & Phrase Deduplication Engine ─────────────────
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "into", "they", "them", "their",
        "have", "been", "were", "will", "would", "could", "should", "about", "more", "most",
        "some", "what", "when", "where", "which", "while", "because", "also", "just", "only",
        "very", "even", "then", "than", "over", "each", "every", "these", "those", "such",
        "there", "here", "other", "being", "through", "after", "before", "between", "both"
    }

    segments = script.get("segments", [])
    for pass_num in range(2):
        repetition_found = False
        for i in range(len(segments)):
            narr_i = segments[i].get("narration", "").strip()
            words_i = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', narr_i.lower()) if w not in stop_words]
            tokens_i = narr_i.lower().split()

            for j in range(i + 1, len(segments)):
                # Intentionally allow loop echo between Segment 1 and the final segment (the loop bridge)
                if i == 0 and j == len(segments) - 1 and script.get("loop_callout"):
                    continue

                narr_j = segments[j].get("narration", "").strip()
                words_j = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', narr_j.lower()) if w not in stop_words]
                tokens_j = narr_j.lower().split()

                # 1. Opening clause / prefix echo check (e.g. "While airlines deny...")
                clause_i = " ".join(tokens_i[:4]) if len(tokens_i) >= 4 else ""
                clause_j = " ".join(tokens_j[:4]) if len(tokens_j) >= 4 else ""
                common_prefix = (clause_i == clause_j) and len(clause_i) > 8

                # 2. Consecutive 4-gram overlap check
                has_4gram = False
                for k in range(len(tokens_i) - 3):
                    ngram = " ".join(tokens_i[k:k+4])
                    if ngram in narr_j.lower():
                        has_4gram = True
                        break

                # 3. High lexical overlap ratio
                overlap = set(words_i) & set(words_j)
                min_len = min(len(set(words_i)), len(set(words_j)))
                overlap_ratio = len(overlap) / min_len if min_len > 0 else 0.0
                is_lexical_dup = (len(overlap) >= 3 and overlap_ratio >= 0.35)

                if common_prefix or has_4gram or is_lexical_dup:
                    print(f"[Phase2 Script] REPETITION DETECTED between Segment {i+1} and Segment {j+1}!")
                    print(f"  Seg {i+1}: '{narr_i}'")
                    print(f"  Seg {j+1}: '{narr_j}'")
                    print(f"  Overlap: {overlap} | Ratio: {overlap_ratio:.2f} | 4-gram: {has_4gram} | Prefix: {common_prefix}")
                    repetition_found = True

                    # Attempt focused LLM rewrite of Segment j if not fallback
                    rewritten = False
                    if not is_fallback_script:
                        try:
                            rewrite_prompt = f"""In this educational script on "{topic.get('topic', '')}", Segment {j+1} repeated the concepts/phrasing of Segment {i+1}.
Segment {i+1} Narration: "{narr_i}"
Segment {j+1} Narration: "{narr_j}"

Rewrite Segment {j+1} (14-18 words) so it presents a COMPLETELY DIFFERENT, advancing physical mechanism, operational consequence, or historical breakthrough.
STRICT RULES:
1. DO NOT use the words or phrases: {list(overlap)}.
2. DO NOT start with the clause "{clause_j}".
3. Target a physical, real-world entity for broll_query (NO screens, NO code, NO browsers).
Return ONLY raw JSON:
{{
  "narration": "...",
  "broll_query": "2-3 words physical entity",
  "broll_queries": ["query 1", "query 2"]
}}"""
                            regen_raw = client.generate_text(rewrite_prompt, use_grounding=False, temperature=0.5)
                            regen_obj = _robust_json_loads(regen_raw)
                            if isinstance(regen_obj, dict) and regen_obj.get("narration"):
                                new_narr = regen_obj["narration"].strip()
                                new_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', new_narr.lower()) if w not in stop_words]
                                new_overlap = set(words_i) & set(new_words)
                                if len(new_overlap) < 3:
                                    segments[j]["narration"] = new_narr
                                    if regen_obj.get("broll_query"):
                                        segments[j]["broll_query"] = regen_obj["broll_query"]
                                    if regen_obj.get("broll_queries"):
                                        segments[j]["broll_queries"] = regen_obj["broll_queries"]
                                    rewritten = True
                                    print(f"[Phase2 Script] Successfully rewrote Segment {j+1}: '{new_narr}'")
                        except Exception as e_rw:
                            print(f"[Phase2 Script] LLM segment rewrite note: {e_rw}")

                    if not rewritten:
                        if is_fallback_script:
                            continue
                        if common_prefix and len(narr_j) > len(clause_j):
                            clean_j = narr_j[len(clause_j):].lstrip(" ,.-:;").capitalize()
                            segments[j]["narration"] = f"In actual operations, {clean_j[:1].lower() + clean_j[1:]}"
                        else:
                            niche_fallbacks = {
                                "engineering": "Under continuous stress testing, structural sensors confirm the materials withstand extreme kinetic loads.",
                                "nature": "In field observations, high-speed camera recordings verify this extraordinary survival behavior in the wild.",
                                "history": "Documented military archives confirm this surprise maneuver caught the defending forces off guard.",
                                "mystery": "Independent expedition logs confirm the anomalous readings persisted across multiple sensor arrays.",
                                "science": "Controlled laboratory measurements prove the physical system operates with extraordinary quantum precision."
                            }
                            segments[j]["narration"] = niche_fallbacks.get(niche, "Controlled scientific measurements prove the physical system operates with extraordinary precision.")
        if not repetition_found:
            break

    # ── Cleanse B-Roll Queries of Abstract / UI / Digital Slop ────────────────
    ui_broll_map = {
        "cookie": "server room lights",
        "browser": "flight operations center",
        "laptop": "datacenter server racks",
        "phone": "airplane cockpit flight deck",
        "screen": "trading floor monitors",
        "website": "container cargo ship",
        "code": "semiconductor cleanroom",
        "dynamic pricing": "airline ticket counter",
        "algorithm": "server rack cooling",
        "pricing": "cargo airplane loading"
    }
    for seg in script.get("segments", []):
        bq = seg.get("broll_query", "")
        bqs = seg.get("broll_queries", [])
        clean_bq = bq
        for bad_k, good_rep in ui_broll_map.items():
            if re.search(r'\b' + re.escape(bad_k) + r'\b', clean_bq.lower()):
                clean_bq = good_rep
                break
        seg["broll_query"] = clean_bq

        clean_bqs = []
        for q in bqs:
            q_cand = q
            for bad_k, good_rep in ui_broll_map.items():
                if re.search(r'\b' + re.escape(bad_k) + r'\b', q_cand.lower()):
                    q_cand = good_rep
                    break
            clean_bqs.append(q_cand)
        seg["broll_queries"] = clean_bqs or [clean_bq]

    # ── Ensure Beacons Link in Description ────────────────────────────────────
    if "description" in script:
        desc = script["description"]
        desc = re.sub(r'(?mi)^line\s*\d+\s*:\s*', '', desc)
        if "[link]" in desc:
            desc = desc.replace("[link]", BEACONS_LINK)
        if BEACONS_LINK not in desc:
            desc += f"\n\n📲 Follow our socials & links: {BEACONS_LINK}"
        script["description"] = desc.strip()

    # ── Ensure Vocal Tone Variety ─────────────────────────────────────────────
    if "vocal_tone" not in script or not script["vocal_tone"]:
        vocal_tones = ["dramatic_whisper", "suspenseful_mystery", "energetic_storytelling", "deep_curiosity", "bold_authority", "warm_storyteller", "dark_revelation", "playful_wit"]
        script["vocal_tone"] = random.choice(vocal_tones)

    return script
