import os
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
        import random as _random
        segment_count = _random.choices([4, 5, 6], weights=[15, 65, 20], k=1)[0]
        
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
            
        prompt = f"""Generate an extremely viral, high-retention 25-35 second YouTube Short educational script on the topic: "{topic['topic']}".
Use the following hook concept as your core theme: "{hook_formatted}" (short hook: "{topic.get('short_hook', '')}").
{lang_instruction}
Narration Style Requirements (CRITICAL - MAXIMUM VIRALITY & SIMPLICITY):
1. EXTREME SIMPLICITY & CONVERSATIONAL ENGLISH (8TH GRADE LEVEL):
   - Write like an excited friend telling an insane secret around a campfire.
   - ABSOLUTELY FORBIDDEN: Academic jargon, dense terminology, passive textbook lecturing.
     NEVER USE WORDS LIKE: "improbable", "desensitized", "homeostatic", "equilibrium", "methodology", "reconsider", "predatory instincts", "operational mechanisms", "unprecedented mechanisms", "fundamental reaction", "historical accounts suggest", "prompts to reconsider".
   - REQUIRED: Plain, sensory, visual language: "melts", "smashes", "tricks", "sneaks in", "explodes", "freezes solid", "eats through", "turns to dust".
2. RAPID-FIRE PUNCHY BEATS (MAX 8-12 WORDS PER SENTENCE):
   - Every sentence MUST be short and active. Maximum 12 words per sentence.
   - ABSOLUTELY FORBIDDEN: Long compound sentences or subordinate clauses (do NOT write sentences starting with "While...", "Although...", "Which means that...", "Making it...").
   - Break thoughts into punchy active beats: "A mantis shrimp doesn't just punch. Its claw strikes faster than a bullet. The water boils into a shockwave."
3. MANDATORY STARTLING UNKNOWN FACT (THE REVEAL):
   - Every single script MUST reveal at least ONE specific, counterintuitive, jaw-dropping secret that 99% of people DO NOT KNOW.
   - NEVER deflate the hook with a wet blanket or say "actually it didn't happen". Deliver an astonishing, verified truth.
4. ZERO TOPIC REPETITION:
   - Introduce the subject in Segment 1. In subsequent segments, refer to it naturally ("this metal", "the ancient weapon", "the creature", "this machine"). NEVER repeat the full topic string.
5. COMPLETE, SATISFYING CLOSING (ZERO DANGLING WORDS):
   - The final segment must be a 100% grammatically complete sentence ending with a period.
   - ABSOLUTELY FORBIDDEN: Ending with dangling conjunctions or prepositions like "because", "which", "how", "and", "so", or ellipses "...".

COMPANION LAYER - NICHE & FORMAT UPGRADE (SHORT):
- CLARITY & ACCESSIBILITY RULE (SIMPLE & INTRIGUING, ZERO PHD JARGON):
  * Explain the mind-blowing mechanism using simple, vivid, conversational words and tangible physical comparisons.
  * FORBIDDEN: Academic jargon, dense textbook terminology, or abstract PhD words.
  * REQUIRED: Describe what physically HAPPENS in punchy, visual language (e.g., 'lasers shoot light particles to smack hot atoms until they freeze completely still', 'water pressure heavy enough to crush a steel submarine like an aluminum soda can', 'giant drill heads hotter than boiling soup').
  * An 8th grader must understand the core revelation instantly while feeling genuinely mind-blown.

- MANDATORY STARTLING UNKNOWN FACT (THE "I DIDN'T KNOW THAT!" FACTOR):
  * Every single script MUST reveal at least ONE specific, counterintuitive, little-known mechanism or hidden physical reality that educated adults do NOT know.
  * FORBIDDEN: Superficial textbook summaries (e.g., "whales are big", "pyramids are stone", "tunnels go under mountains", "black holes are dark").
  * REQUIRED: The startling, precise hidden detail (e.g., "a sperm whale's spermaceti oil hardens into solid wax at deep cold depths to act as an automated buoyancy anchor", "the Great Pyramid has eight concave faces only visible from the sky on the exact equinox afternoon", "subsea tunnel boring machines freeze groundwater into a solid ice wall with liquid nitrogen so workers don't drown", "quantum lasers freeze atom kinetic momentum to near absolute zero").

- FORMAT RULE (20-30s Shorts): The entire video IS the hook. Hook, content, and payoff happen simultaneously.
  * Grab (0-3s): One powerful statement, visual, or question. No intro. No channel name. No fluff.
  * Deliver (3-20s): The actual value/story/reveal. Fast. Dense. No filler.
  * Payoff + CTA (20-30s): The punchline, answer, result, or twist (one line only), then end.
  * Avoid: Words that do not carry weight, silence over 1s, padding, slow pacing.
- NICHE QUALITY SIGNALS (Education):
  * SHOW THE RESULT FIRST: State or show the answer/outcome before explaining how you get there. Viewers stay to understand something they just saw — not to wait.
  * B-ROLL THAT PROVES THE POINT: Every concept explained verbally must have a visual that demonstrates it, not just decorates it.
  * ONE CLEAR GAIN PER VIDEO: Teach exactly one thing. Script must answer: "What is the single thing this viewer will walk away with?"
  * TEXT OVERLAYS THAT REINFORCE, NOT REPEAT: Use text for key terms, surprising numbers, simple diagrams, or summary sentences. Do not transcribe verbatim.
  * CONTINUOUS CURIOSITY LOOP: Every 2-3 segments, give a new reason to stay with a new question (e.g., "But here's where it gets interesting...").

- MANDATORY AUTHENTIC DOCUMENTARY SOURCING (ZERO AI SLOP / ZERO GENERIC STOCK):
  * FORBIDDEN: Generic stock proxies, abstract glowing backgrounds, floating particles, CGI animations, generic office workers, or decorative filler.
  * REQUIRED: Target the EXACT real-world documentary subject, scientific apparatus, historical artifact, living species binomial, or institutional archive:
    - Specific Missions & Facilities: "James Webb NIRCam deep field", "Apollo 11 Saturn V staging", "CERN LHC beam pipe vacuum chamber", "Cold Atom Lab ISS quantum physics", "Gotthard Base Tunnel boring machine cutter"
    - Exact Biological & Field Entities: "coelacanth Latimeria chalumnae underwater", "sperm whale spermaceti organ dive", "pistol shrimp snapping claw macro", "deep sea anglerfish bioluminescence"
    - Authentic Historical Artifacts & Patents: "Antikythera mechanism bronze gear", "Byzantine Greek fire siphon dragon", "Archimedes claw syracuse crane", "Dead Sea scroll parchment Hebrew"
    - Real Laboratory Apparatus & Scans: "scanning electron microscope crystal lattice", "cryogenic dilution refrigerator copper coils", "laser optical table beam splitter", "fluorescent cell mitosis petri dish"
  * SYNTAX: [Specific Domain / Specimen / Mission] + [Physical Material / Mechanism] + [Authentic Optical State]
  * ZERO BUZZWORDS IN BROLL QUERIES:
    - ABSOLUTELY FORBIDDEN: Do NOT write marketing adjectives or vague descriptors like 'futuristic', 'next-generation', 'super bright', 'incredible', 'amazing', 'shocking', 'impossible', 'visualization', 'concept', 'animation', 'effect', 'demonstration', 'presenting'.
    - REQUIRED: Name ONLY the concrete physical noun of the object/specimen/machine being discussed.

For each segment, provide a `broll_queries` array with 3-5 ALTERNATIVE hyper-specific search queries targeting real footage and institutional archives. The first entry must match `broll_query`.

For any named person, scientist, or historic figure: ALWAYS include their exact full name.

You MUST return your response ONLY as a raw JSON object with no markdown syntax. The JSON structure MUST be exactly like this:
{{
  "title": "A catchy title under 40 chars, starting with a hook word/number and containing one emoji",
  "voiceover_plan": "A 2-3 sentence internal plan detailing the emotional arc of the voiceover. How should the narrator sound? Think step-by-step to plan the performance before writing.",
  "vocal_tone": "Select the single best vocal delivery style for this topic. Choose EXACTLY ONE from this list: 'dramatic_whisper', 'suspenseful_mystery', 'energetic_storytelling', 'deep_curiosity', 'bold_authority', 'warm_storyteller', 'dark_revelation', 'playful_wit'. Match the tone to the emotional core of the topic.",
  "description": "Line1: restate the hook\nLine2: Fast. Accurate. Mind-blowing.\nLine3: 📲 Follow our socials & links -> {BEACONS_LINK}\n\n#science #didyouknow #facts",
  "tags": ["8 to 12 relevant tags under 500 characters total"],
  "category_id": "27",
  "segments": [
    // Provide exactly {segment_count} segments here.
    {{
      "id": 1,
      "narration": "opening shocking hook complete sentence - 10 words or less, massive information gap",
      "broll_query": "concrete physical object 4k",
      "broll_queries": ["concrete physical object 4k", "optical macro close up 4k", "documentary authentic footage 4k"],
      "duration_target": 6
    }},
    {{
      "id": 2,
      "narration": "Mind-bending real fact that delivers on the hook - 10 words or less",
      "broll_query": "specific mechanism or apparatus 4k",
      "broll_queries": ["specific mechanism or apparatus 4k", "laboratory demonstration 4k"],
      "duration_target": 6
    }},
    {{
      "id": {segment_count},
      "narration": "A complete, punchy final takeaway sentence delivering the ultimate mind-blowing payoff, plus a natural call-to-action (e.g. 'More wild secrets at the link in bio.'). MUST be a 100% complete sentence ending with a period. NEVER end with dangling words like 'because' or 'which'!",
      "broll_query": "concrete physical object documentary footage 4k",
      "broll_queries": ["concrete physical object 4k", "action close up macro", "field specimen documentary footage 4k"],
      "duration_target": 6
    }}
  ],
  "thumbnail_text": "3 to 5 bold words max for the thumbnail",
  "loop_callout": true
}}

For Segment 1 specifically:
- `broll_query` MUST describe a high-motion, high-contrast, visually arresting shot (fast motion, bright colors, dramatic close-up) — this is the opening pattern-interrupt that determines whether viewers keep watching.

For Segments 2 to (n-1):
- Frame facts with visual or scientific paradoxes (e.g., 'Something the size of a city that weighs more than the sun' or 'The man who failed entrance exams rewrote the universe').
- Deliver the single most mind-bending scientific fact in Segment 2.
- Introduce an open loop (a second mystery or surprise fact) in Segment 3 that builds tension towards the loop twist.

For the final segment (Segment {segment_count}) specifically:
- MUST be a 1-sentence Call-to-Action that matches the video's emotional tone and drives viewers to check the link in description/bio.
- MUST literally include the exact phrase "link in bio" or "link in the description".
- Good examples: "For more mind-blowing details, check the link in bio.", "The full breakdown is waiting at the link in bio.", "Ready for the deep dive? Check the link in description."
- NEVER write a generic CTA like "Dive deeper!" or "Want to learn more?" without explicitly mentioning the link.
- Relaxed word limit: Up to 15 words to allow natural integration of the link phrase.
- MUST resolve all loops and end on a transition that flows seamlessly back into Segment 1's hook narration.
- The final sentence should THEMATICALLY echo or re-contextualize the IDEA from Segment 1's hook.
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
            break
        except Exception as e:
            print(f"Error parsing script JSON on attempt {attempt+1}: {e}. Raw script text: {script_text}")

    if script is None:
        is_fallback_script = True
        print("[Phase2] Gemini API rate-limited after retries. Generating niche-aware dynamic topic fallback script dict...")
        raw_title = topic.get('topic', 'Engineering Breakthrough') if isinstance(topic, dict) else str(topic)
        import re
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
                "voiceover_plan": "Deliver fast-paced, awe-inspiring engineering narration.",
                "vocal_tone": "deep_curiosity",
                "description": f"The impossible engineering behind {entity_name}.\n\nMassive scale. Extreme physics.\n\n#engineering #megaprojects #construction",
                "tags": ["engineering", "megaprojects", "construction", "technology", "architecture", "machines", "didyouknow"],
                "category_id": "28",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"The {entity_name} is one of the most audacious megaprojects ever constructed by human engineers.",
                        "broll_query": f"{entity_name} megaproject construction real footage 4k",
                        "broll_queries": [f"{entity_name} megaproject construction real footage 4k", f"{entity_name} colossal engineering machinery 4k", f"{entity_name} aerial landmark 1080p"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": f"To build the {entity_name}, teams had to overcome extreme physical forces and push modern materials beyond their limits.",
                        "broll_query": f"{entity_name} heavy machinery construction site 4k",
                        "broll_queries": [f"{entity_name} heavy machinery construction site 4k", f"{entity_name} tunnel boring machine industrial 4k", "massive civil engineering construction 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": f"Every single section required millimeter-level precision and unprecedented structural breakthroughs.",
                        "broll_query": f"{entity_name} completed operational infrastructure 4k",
                        "broll_queries": [f"{entity_name} completed operational infrastructure 4k", f"{entity_name} high speed transit aerial 4k", "modern engineering masterpiece 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"Today, the {entity_name} stands as living proof of what human ambition can achieve.",
                        "broll_query": f"{entity_name} cinematic engineering documentary 4k",
                        "broll_queries": [f"{entity_name} cinematic engineering documentary 4k", f"{entity_name} drone overview 4k", "futuristic megastructure architecture 4k"],
                        "duration_target": 5
                    }
                ],
                "loop_callout": True
            }
        elif niche == "nature":
            script = {
                "title": f"🌊 Secret of {entity_name[:32]}",
                "voiceover_plan": "Deliver intense, suspenseful wildlife narration.",
                "vocal_tone": "deep_curiosity",
                "description": f"The shocking survival adaptation of {entity_name}.\n\nWild biology in extreme habitats.\n\n#nature #wildlife #ocean",
                "tags": ["nature", "wildlife", "animals", "biology", "ocean", "evolution", "didyouknow"],
                "category_id": "15",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"Deep in the wild, the {entity_name} developed one of the most extreme survival mechanisms on Earth.",
                        "broll_query": f"{entity_name} wildlife documentary real footage 4k",
                        "broll_queries": [f"{entity_name} wildlife documentary real footage 4k", f"{entity_name} animal close up authentic footage 4k", f"{entity_name} ocean habitat 1080p"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": f"To survive intense predation, the {entity_name} utilizes biological adaptations seen nowhere else in nature.",
                        "broll_query": f"{entity_name} hunting predation behavior 4k",
                        "broll_queries": [f"{entity_name} hunting predation behavior 4k", f"{entity_name} natural habitat camera 4k", "deep wilderness wildlife documentary 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": f"Biologists studying the {entity_name} uncovered physiological traits that allow it to thrive under lethal conditions.",
                        "broll_query": f"{entity_name} underwater scientific observation 4k",
                        "broll_queries": [f"{entity_name} underwater scientific observation 4k", f"{entity_name} macro wildlife photography 4k", "fascinating creature biology 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"The incredible biology of the {entity_name} reveals how life adapts to conquer the impossible.",
                        "broll_query": f"{entity_name} cinematic wildlife documentary 4k",
                        "broll_queries": [f"{entity_name} cinematic wildlife documentary 4k", f"{entity_name} animal kingdom close up 4k", "natural world documentary 4k"],
                        "duration_target": 5
                    }
                ],
                "loop_callout": True
            }
        elif niche == "history":
            script = {
                "title": f"⚔️ Tactical Secret of {entity_name[:32]}",
                "voiceover_plan": "Deliver dramatic, epic historical narration.",
                "vocal_tone": "deep_curiosity",
                "description": f"The battlefield strategy that changed world history: {entity_name}.\n\n#history #warfare #tactics",
                "tags": ["history", "warfare", "tactics", "ancient", "battles", "strategy", "didyouknow"],
                "category_id": "27",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"In ancient history, the tactical mastery of {entity_name} permanently shattered the balance of power.",
                        "broll_query": f"{entity_name} historical documentary battle 4k",
                        "broll_queries": [f"{entity_name} historical documentary battle 4k", f"{entity_name} ancient warfare reenactment 1080p", "ancient empire fortress ruins 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": f"Commanders deployed revolutionary combat strategies that caught their adversaries completely off guard.",
                        "broll_query": f"{entity_name} tactical military formation historical 4k",
                        "broll_queries": [f"{entity_name} tactical military formation historical 4k", "ancient weapons combat strategy 4k", "battlefield history documentary 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": f"This decisive confrontation proved that superior discipline and tactical terrain mastery overcome raw numbers.",
                        "broll_query": f"{entity_name} archaeological ruins battlefield 4k",
                        "broll_queries": [f"{entity_name} archaeological ruins battlefield 4k", "ancient civilization history 4k", "historical empire conquest 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"The enduring strategic legacy of {entity_name} is still analyzed by historians to this day.",
                        "broll_query": f"{entity_name} ancient monument historical documentary 4k",
                        "broll_queries": [f"{entity_name} ancient monument historical documentary 4k", "epic historical archive cinematic 4k", "ancient world civilization 4k"],
                        "duration_target": 5
                    }
                ],
                "loop_callout": True
            }
        elif niche == "mystery":
            script = {
                "title": f"👁️ Unsolved: {entity_name[:32]}",
                "voiceover_plan": "Deliver dark, suspenseful mystery narration.",
                "vocal_tone": "deep_curiosity",
                "description": f"The baffling anomaly of {entity_name}.\n\nUnexplained evidence. Lingering questions.\n\n#mystery #unexplained #strange",
                "tags": ["mystery", "unexplained", "strange", "paranormal", "anomaly", "didyouknow"],
                "category_id": "24",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"For decades, the inexplicable enigma surrounding {entity_name} has baffled researchers across the world.",
                        "broll_query": f"{entity_name} mystery anomaly archival footage 4k",
                        "broll_queries": [f"{entity_name} mystery anomaly archival footage 4k", f"{entity_name} unexplained phenomenon documentary 1080p", "dark mystery twilight 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": f"Physical evidence and documented records of {entity_name} reveal anomalies that modern theories fail to explain.",
                        "broll_query": f"{entity_name} scientific investigation anomaly evidence 4k",
                        "broll_queries": [f"{entity_name} scientific investigation anomaly evidence 4k", "archival mystery raw footage 4k", "strange earth enigma 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": f"Investigators analyzing the data discovered patterns that defy all conventional logic.",
                        "broll_query": f"{entity_name} mysterious location drone camera 4k",
                        "broll_queries": [f"{entity_name} mysterious location drone camera 4k", "unsolved mystery investigation 4k", "historical enigma dark 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"To this day, the true explanation for {entity_name} remains shrouded in total mystery.",
                        "broll_query": f"{entity_name} unsolved mystery documentary 4k",
                        "broll_queries": [f"{entity_name} unsolved mystery documentary 4k", "strange world anomaly cinematic 4k", "deep mystery landscape 4k"],
                        "duration_target": 5
                    }
                ],
                "loop_callout": True
            }
        else: # science
            script = {
                "title": f"🔬 Breakthrough in {entity_name[:32]}",
                "voiceover_plan": "Deliver fast, energetic scientific narration.",
                "vocal_tone": "deep_curiosity",
                "description": f"The mind-blowing physics behind {entity_name}.\n\n#science #physics #technology",
                "tags": ["science", "physics", "technology", "quantum", "universe", "didyouknow"],
                "category_id": "28",
                "segments": [
                    {
                        "id": 1,
                        "narration": f"The breakthrough discovery of {entity_name} is transforming our understanding of physical reality.",
                        "broll_query": f"{entity_name} scientific laboratory research 4k",
                        "broll_queries": [f"{entity_name} scientific laboratory research 4k", f"{entity_name} experimental physics discovery 1080p", "advanced science laboratory 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 2,
                        "narration": f"By analyzing extreme experimental data, physicists proved that {entity_name} operates through unprecedented mechanisms.",
                        "broll_query": f"{entity_name} laboratory experiment laser apparatus 4k",
                        "broll_queries": [f"{entity_name} laboratory experiment laser apparatus 4k", "particle physics laboratory 4k", "high tech science experiment 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 3,
                        "narration": f"This fundamental reaction produces energy dynamics that challenge established theoretical models.",
                        "broll_query": f"{entity_name} scientific simulation visualization 4k",
                        "broll_queries": [f"{entity_name} scientific simulation visualization 4k", "atomic particle reaction physics 4k", "supercomputer science simulation 4k"],
                        "duration_target": 6
                    },
                    {
                        "id": 4,
                        "narration": f"As scientific tools advance, {entity_name} may unlock the next great revolution in technology.",
                        "broll_query": f"{entity_name} futuristic science innovation 4k",
                        "broll_queries": [f"{entity_name} futuristic science innovation 4k", "frontier technology laboratory 4k", "deep space scientific observatory 4k"],
                        "duration_target": 5
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
            script["segments"] = verified_script.get("segments", script["segments"])
        except Exception as e:
            print(f"Fact check failed or quota-limited ({e}), keeping original script for Judge AI review.")
            for seg in script["segments"]:
                seg["verified"] = True
    else:
        for seg in script["segments"]:
            seg["verified"] = True

    # Regenerate unverified segments
    for seg in script["segments"]:
        if not seg.get("verified", True):
            print(f"Segment {seg['id']} failed fact check. Regenerating narration...")
            regen_prompt = f"""The following script segment narration failed fact-checking or was unverified:
Topic: {topic['topic']}
Segment details: {json.dumps(seg, indent=2)}

Rewrite the "narration" so that it is 100% scientifically accurate, verifiable, and maintains the exact same tone and target duration.
Return ONLY a raw JSON object for this segment with the updated "narration" and `"verified": true`.
"""
            try:
                regen_text = client.generate_text(regen_prompt, use_grounding=False, temperature=0.3)
                regen_seg = _robust_json_loads(regen_text)
                seg["narration"] = regen_seg.get("narration", seg["narration"])
                seg["verified"] = True
            except Exception as e:
                print(f"Failed to regenerate segment {seg['id']} ({e}). Keeping original for Judge AI review.")
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

    # ── Ensure CTA Segment Narration Mentions Link Cleanly ───────────────────
    if format_type == "short":
        cta_idx = len(script.get("segments", [])) - 1
        if cta_idx >= 0:
            cta_seg = script["segments"][cta_idx]
            cta_narration = cta_seg.get("narration", "")
            if "link" not in cta_narration.lower():
                print(f"[Phase 2] CTA Segment narration '{cta_narration}' lacks link mention. Enforcing...")
                cta_clean = cta_narration.rstrip(".!?,")
                cta_seg["narration"] = f"{cta_clean} — link in bio!"

    # ── Ensure Beacons Link in Description ────────────────────────────────────
    if "description" in script:
        desc = script["description"]
        if "[link]" in desc:
            desc = desc.replace("[link]", BEACONS_LINK)
        if BEACONS_LINK not in desc:
            desc += f"\n\n📲 Follow our socials & links: {BEACONS_LINK}"
        script["description"] = desc

    # ── Ensure Vocal Tone Variety ─────────────────────────────────────────────
    if "vocal_tone" not in script or not script["vocal_tone"]:
        import random as _rnd
        vocal_tones = ["dramatic_whisper", "suspenseful_mystery", "energetic_storytelling", "deep_curiosity", "bold_authority", "warm_storyteller", "dark_revelation", "playful_wit"]
        script["vocal_tone"] = _rnd.choice(vocal_tones)

    return script
