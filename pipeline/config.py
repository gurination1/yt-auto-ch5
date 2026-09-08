import os
try:
    from dotenv import load_dotenv
    load_dotenv()
    for ep in [".env", "../.env", "../../.env", "/mnt/g/yt-auto-fleet/.env"]:
        if os.path.exists(ep):
            load_dotenv(ep, override=False)
except Exception:
    pass

# Auto-load local_env.sh if present to populate environment variables
def _autoload_local_env():
    for env_path in [".env", "local_env.sh", "../local_env.sh",  "/root/local_env.sh"]:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.startswith("export "):
                            line = line[7:]
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k and k not in os.environ and v:
                                os.environ[k] = v
            except Exception:
                pass

_autoload_local_env()

# ── Gemini Key Pool ──────────────────────────────────────────────────────────
def _load_keys() -> list[str]:
    keys: list[str] = []
    multi = os.environ.get("GEMINI_API_KEYS", "").strip()
    if multi:
        keys.extend(k.strip() for k in multi.split(",") if k.strip())
    single = os.environ.get("GEMINI_API_KEY", "").strip()
    if single and not keys:
        keys.append(single)
    return list(dict.fromkeys(keys))

GEMINI_API_KEYS: list[str] = _load_keys()
GEMINI_API_KEY: str = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""

GEMINI_JUDGE_API_KEY: str = os.environ.get("GEMINI_JUDGE_API_KEY", "").strip() or GEMINI_API_KEY

# ── Other APIs ───────────────────────────────────────────────────────────────
PEXELS_API_KEY   = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_API_KEY  = os.environ.get("PIXABAY_API_KEY", "")
COVERR_API_KEY   = os.environ.get("COVERR_API_KEY", "")
NASA_API_KEY     = os.environ.get("NASA_API_KEY", "DEMO_KEY")
KLIPY_API_KEY    = os.environ.get("KLIPY_API_KEY", "")
FREESOUND_API_KEY = os.environ.get("FREESOUND_API_KEY", "")

# ── YouTube OAuth ────────────────────────────────────────────────────────────
YT_CLIENT_ID     = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN", "")

# ── Gemini Models ────────────────────────────────────────────────────────────
GEMINI_FLASH        = "gemini-2.5-flash"
GEMINI_FLASH_BACKUP = "gemini-2.5-flash-lite"
GEMINI_PRO          = "gemini-2.5-flash"
GEMINI_TTS_MODEL    = "gemini-2.5-flash-preview-tts"
GEMINI_API_BASE     = "https://generativelanguage.googleapis.com/v1beta"

GEMINI_VOICES    = ["Fenrir", "Puck", "Charon", "Orus", "Kore", "Aoede"]
EDGE_VOICES      = ["en-US-GuyNeural", "en-US-AndrewNeural", "en-US-ChristopherNeural", "en-US-EricNeural", "en-US-BrianNeural", "en-US-AvaNeural", "en-US-EmmaNeural", "en-US-SteffanNeural"]
KOKORO_VOICES    = ["af_heart","af_bella","af_nicole","af_sarah","af_sky","af_aoede","am_adam","am_michael","am_fenrir","am_puck"]

# ── Video Specs ──────────────────────────────────────────────────────────────
SHORTS_W, SHORTS_H = 1080, 1920
LONG_W,   LONG_H   = 1920, 1080
FPS                 = 30
TOPIC_LOG_SIZE      = 90

HOOK_PATTERNS = [
    "The {topic} fact that breaks a rule you learned in school",
    "In exactly 30 seconds you'll never see {topic} the same way",
    "Scientists found something inside {topic} that shouldn't exist",
    "The {topic} detail that 99% of people never notice — even experts",
    "What {topic} does when no one is watching will disturb you",
    "The one thing about {topic} that every textbook gets wrong",
    "This single {topic} fact overturns 100 years of assumptions",
    "You've seen {topic} your whole life. You've never actually seen it.",
]

THUMBNAIL_LAYOUTS = [
    "dark_top_bar",
    "centered_gradient",
    "bottom_third",
    "split_left",
]

# ── Channel Boundary & Topic Isolation (Channel 5: Megaprojects & Engineering) ──
CHANNEL_NICHE = os.environ.get("CHANNEL_NICHE", "engineering")

CHANNEL_BOUNDARY = {
    "channel_id": "ch5",
    "name": "Channel 5: Megaprojects & Engineering",
    "niche_description": "Colossal tunnel boring machines (TBMs), subsea immersed tunnels, mega hydroelectric dams, extreme heavy machinery (Bagger 288/293, crawler-transporters, super-cranes), and supertall skyscraper tuned mass dampers and seismic engineering.",
    "allowed_subclusters": [
        "colossal tunnel boring machines (TBMs) and deep subterranean engineering",
        "subsea immersed tunnels, undersea rail crossings, and precast tubes",
        "colossal hydroelectric mega-dams, concrete gravity barriers, and water redirection",
        "extreme heavy machinery, super-cranes, crawler-transporters, and bucket-wheel excavators",
        "supertall skyscraper engineering, tuned mass dampers, and aerodynamic vortex shedding"
    ],
    "strict_negative_constraints": [
        "NO space science, astronomy, astrophysics, telescopes, cosmology, rockets, or Mars/Moon missions.",
        "NO financial markets, hedge funds, crypto, stocks, billionaire trading, private equity, or tax-loss harvesting.",
        "NO animals, wildlife, zoology, insects, marine biology, or nature documentaries.",
        "NO ancient historical battles, swords, shields, Roman warfare, or medieval knights."
    ],
    "negative_keywords": [
        "astronomy",
        "astrophysics",
        "telescope",
        "james webb",
        "galaxy",
        "orbit",
        "mars rover",
        "moon landing",
        "exoplanet",
        "dark energy",
        "supernova",
        "black hole",
        "cosmic ray",
        "solar storm",
        "spacewalk",
        "rocket launch",
        "crypto",
        "bitcoin",
        "ethereum",
        "hedge fund",
        "stock market",
        "private equity",
        "tax-loss",
        "wall street",
        "venture capital",
        "saylor",
        "asness",
        "goodhart",
        "billionaire wealth",
        "family office",
        "animal",
        "creature",
        "predator",
        "biology",
        "zoology",
        "wildlife",
        "insect",
        "species",
        "reptile",
        "shark",
        "ancient battle",
        "roman army",
        "roman legion",
        "gladiator",
        "medieval siege",
        "trebuchet",
        "sword fight",
        "phalanx"
    ]
}

CHANNEL_SUBCLUSTERS = CHANNEL_BOUNDARY["allowed_subclusters"]
SCIENCE_SUBCLUSTERS = CHANNEL_SUBCLUSTERS
NATURE_SUBCLUSTERS = CHANNEL_SUBCLUSTERS
NATURAL_WORLD_SUBCLUSTERS = CHANNEL_SUBCLUSTERS
HISTORY_SUBCLUSTERS = CHANNEL_SUBCLUSTERS
MYSTERY_SUBCLUSTERS = CHANNEL_SUBCLUSTERS
ENGINEERING_SUBCLUSTERS = CHANNEL_SUBCLUSTERS
NICHE_SUBCLUSTERS = CHANNEL_SUBCLUSTERS

YT_CATEGORY_EDUCATION = "27"
YT_CATEGORY_SCIENCE   = "28"
YT_CATEGORY_DEFAULT   = "28"
NASA_BROLL_ENABLED    = True

RICH_FALLBACK_TOPICS = [
    {
        "topic": "The Bagger 293: The 14,000-ton colossal bucket-wheel excavator that holds the record for heaviest land vehicle",
        "short_hook": "This machine is heavier than 30 Boeing 747s!",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "extreme heavy machinery, super-cranes, crawler-transporters, and bucket-wheel excavators"
    },
    {
        "topic": "The Gotthard Base Tunnel: How four colossal TBMs bored 57 kilometers beneath the Alps under 2,000 meters of granite",
        "short_hook": "How did engineers drill 57 kilometers under mountains?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal tunnel boring machines (TBMs) and deep subterranean engineering"
    },
    {
        "topic": "The Taipei 101 Tuned Mass Damper: The 660-ton golden pendulum suspended across five floors to counteract typhoon sway",
        "short_hook": "A 660-ton golden ball saves this skyscraper.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "supertall skyscraper engineering, tuned mass dampers, and aerodynamic vortex shedding"
    },
    {
        "topic": "The Fehmarnbelt Fixed Link: The 18-kilometer immersed tunnel sinking 73,000-ton concrete elements onto the seabed",
        "short_hook": "How engineers sink massive concrete tunnels under oceans.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "subsea immersed tunnels, undersea rail crossings, and precast tubes"
    },
    {
        "topic": "The Three Gorges Dam: The colossal 2.3-kilometer concrete gravity barrier holding 40 billion cubic meters of water",
        "short_hook": "This mega dam holds 40 billion tons of water.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal hydroelectric mega-dams, concrete gravity barriers, and water redirection"
    },
    {
        "topic": "The NASA Crawler-Transporter: The 3,000-ton tracked giant moving 18-million-pound launch loads on laser-leveled roads",
        "short_hook": "The 3,000-ton machine that moves launch rockets.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "extreme heavy machinery, super-cranes, crawler-transporters, and bucket-wheel excavators"
    },
    {
        "topic": "The Channel Tunnel TBMs: How French and British boring machines met 50 meters under the sea with millimeter precision",
        "short_hook": "Two tunneling machines met under the sea with millimeter accuracy.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal tunnel boring machines (TBMs) and deep subterranean engineering"
    },
    {
        "topic": "The Akashi Kaikyo Bridge: The 4-kilometer suspension bridge that survived a 7.2 magnitude earthquake mid-construction",
        "short_hook": "This bridge survived a massive earthquake mid-construction.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "subsea immersed tunnels, undersea rail crossings, and precast tubes"
    },
    {
        "topic": "The Big Bertha TBM: The 57-foot-diameter monster cutterhead built to dig Seattle's two-mile subterranean highway",
        "short_hook": "The world's widest tunnel drill dug under an entire city.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal tunnel boring machines (TBMs) and deep subterranean engineering"
    },
    {
        "topic": "The Millau Viaduct: The French cable-stayed bridge standing 343 meters tall, piercing above the Tarn Valley cloud ceiling",
        "short_hook": "The bridge taller than the Eiffel Tower built above clouds.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "subsea immersed tunnels, undersea rail crossings, and precast tubes"
    },
    {
        "topic": "The Panama Canal Expansion: The colossal 3,000-ton rolling lock gates engineered to transit neo-Panamax supertankers",
        "short_hook": "How 3,000-ton rolling gates lift ocean ships across mountains.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal hydroelectric mega-dams, concrete gravity barriers, and water redirection"
    },
    {
        "topic": "The Shanghai Tower Eddy Current Damper: The 1,000-ton stabilization system using magnetic induction at 632 meters",
        "short_hook": "A 1,000-ton magnetic damper stabilizes this mega skyscraper.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "supertall skyscraper engineering, tuned mass dampers, and aerodynamic vortex shedding"
    },
    {
        "topic": "The Chesapeake Bay Bridge-Tunnel: The 17-mile crossing that dives beneath shipping channels via prefabricated sunken tubes",
        "short_hook": "The highway that dives beneath ocean shipping channels.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "subsea immersed tunnels, undersea rail crossings, and precast tubes"
    },
    {
        "topic": "The Itaipu Dam: The hydroelectric mega-barrier built with enough concrete to construct 210 Olympic stadiums",
        "short_hook": "The mega-dam built with concrete for 210 stadiums.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal hydroelectric mega-dams, concrete gravity barriers, and water redirection"
    },
    {
        "topic": "The Liebherr LR 13000: The most powerful crawler crane on Earth capable of lifting 3,000 metric tons in one hoist",
        "short_hook": "The monster crane capable of lifting 3,000 tons.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "extreme heavy machinery, super-cranes, crawler-transporters, and bucket-wheel excavators"
    },
    {
        "topic": "The Seikan Undersea Rail Tunnel: The 53-kilometer Japanese tunnel bored through explosive undersea fault fractures",
        "short_hook": "Japan's 53-kilometer train tunnel beneath the ocean floor.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal tunnel boring machines (TBMs) and deep subterranean engineering"
    },
    {
        "topic": "The Danyang-Kunshan Grand Bridge: The 164-kilometer high-speed railway viaduct crossing lakes on 10,000 concrete pillars",
        "short_hook": "The 164-kilometer bridge that spans across rivers and lakes.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "subsea immersed tunnels, undersea rail crossings, and precast tubes"
    },
    {
        "topic": "The Marmaray Undersea Tunnel: The seismic immersed rail tube laid 60 meters beneath the turbulent Bosphorus strait",
        "short_hook": "How engineers built an earthquake-proof tunnel under the Bosphorus.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "subsea immersed tunnels, undersea rail crossings, and precast tubes"
    },
    {
        "topic": "The Oosterscheldekering Storm Barrier: The 9-kilometer Dutch engineering marvel featuring 62 hydraulic sliding steel gates",
        "short_hook": "How the Dutch built 62 giant steel gates against the sea.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal hydroelectric mega-dams, concrete gravity barriers, and water redirection"
    },
    {
        "topic": "The Burj Khalifa Foundation: How 192 friction piles driven 50 meters into desert sediment support a half-million-ton tower",
        "short_hook": "How desert sand holds up a half-million-ton skyscraper.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "supertall skyscraper engineering, tuned mass dampers, and aerodynamic vortex shedding"
    },
    {
        "topic": "The BelAZ 75710 Haul Truck: The world's largest dump truck powered by dual 16-cylinder diesel engines hauling 450 tons",
        "short_hook": "The two-story dump truck that carries 450 tons of rock.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "extreme heavy machinery, super-cranes, crawler-transporters, and bucket-wheel excavators"
    },
    {
        "topic": "The Jinping Underground Laboratory: The 2,400-meter deep rock cavern accessed by a 6-kilometer tunnel under Mount Jinping",
        "short_hook": "The deepest subterranean laboratory on Earth under a mountain.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal tunnel boring machines (TBMs) and deep subterranean engineering"
    },
    {
        "topic": "The Pioneering Spirit Megaship: The world's largest construction vessel that lifts whole 48,000-ton offshore platforms",
        "short_hook": "The giant ship that lifts entire 48,000-ton oil platforms.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "extreme heavy machinery, super-cranes, crawler-transporters, and bucket-wheel excavators"
    },
    {
        "topic": "The Shimizu Mega-City Pyramid Concept: The 2,000-meter carbon-truss geometric city planned to house 1 million residents",
        "short_hook": "The proposed 2,000-meter pyramid city for 1 million people.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "supertall skyscraper engineering, tuned mass dampers, and aerodynamic vortex shedding"
    },
    {
        "topic": "The Lake Mead Intake No. 3: How engineers used a deep-water TBM to drill directly into the floor of a 400-foot reservoir",
        "short_hook": "Drilling a giant tunnel into the floor of a 400-foot reservoir.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "colossal tunnel boring machines (TBMs) and deep subterranean engineering"
    }
]

def validate_config():
    missing = []
    if not GEMINI_API_KEYS:
        missing.append("GEMINI_API_KEY or GEMINI_API_KEYS")
    
    check_vars = []
    if PEXELS_API_KEY:
        check_vars.append(("PEXELS_API_KEY", PEXELS_API_KEY))
    if os.environ.get("DISABLE_YT_UPLOAD") != "1":
        check_vars.extend([
            ("YT_CLIENT_ID", YT_CLIENT_ID),
            ("YT_CLIENT_SECRET", YT_CLIENT_SECRET),
            ("YT_REFRESH_TOKEN", YT_REFRESH_TOKEN)
        ])
    for var, val in check_vars:
        if not val:
            missing.append(var)
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")
    n = len(GEMINI_API_KEYS)
    print(f"[Config] {n} Gemini generation key(s) loaded.")
    if GEMINI_JUDGE_API_KEY != GEMINI_API_KEY:
        print("[Config] Separate GEMINI_JUDGE_API_KEY active — Judge uses its own quota.")
    if COVERR_API_KEY:
        print("[Config] Coverr API: enabled (cinematic B-roll tier active).")
    if NASA_API_KEY:
        print(f"[Config] NASA API: enabled (key={'DEMO_KEY (rate-limited)' if NASA_API_KEY == 'DEMO_KEY' else 'custom'}).")
    if KLIPY_API_KEY:
        print("[Config] Klipy API: enabled (GIF/meme B-roll tier active).")
    if FREESOUND_API_KEY:
        print("[Config] Freesound API: enabled (CC0 ambient music tier active).")

# ── Social / Beacons Link ───────────────────────────────────────────────────
BEACONS_LINK = os.environ.get("BEACONS_LINK", "https://beacons.ai/edu_fun")

# ── Fleet Niche Profiles & Digital Fingerprints ──────────────────────────────
FLEET_NICHE_PROFILES = {
    "science": {
        "channel_id": "ch1",
        "name": "Science & Frontier Tech",
        "gemini_voice": "Fenrir",
        "kokoro_voice": "am_adam",
        "edge_voice": "en-US-GuyNeural",
        "cadence_speed": 1.02,
        "vocal_tone": "bold_authority",
        "persona_desc": "precise, analytical, 1.02x",
        "subtitle_fonts": ["Rajdhani", "Montserrat", "Bebas Neue"],
        "c_base": "&H00FFFFFF&",          # Base: Pure White (#FFFFFF)
        "c_active": "&H00FFE500&",        # Active: Electric Cyan (#00E5FF)
        "c_power": "&H00FF8800&",         # Power Accent: Neon Blue/Orange
        "outline_color": "&H00100505&",   # Outline: 9px #050510 (obsidian navy)
        "shadow_color": "&H80000000&",    # Shadow: 3px
        "outline_w": 9,
        "shadow_d": 3,
        "blur": 1,
        "margin_v": 440,
        "procedural_chords": [
            [("D", "min"), ("G", "maj"), ("C", "maj"), ("A", "min")],
            [("E", "min"), ("A", "min"), ("D", "maj"), ("B", "min")],
            [("C", "maj"), ("A", "min"), ("F", "maj"), ("G", "maj")],
        ],
        "music_bpm": 120,
        "foley_type": "digital_tech",
        "ducking": {
            "attack": 15,
            "release": 180,
            "ratio": 4.0,
            "threshold": 0.07,
            "music_vol": 0.22,
            "sfx_vol": 0.28,
        },
        "container_metadata": {
            "artist": "Axiom Lab Studios / Science & Frontier Tech",
            "genre": "Science & Technology / Quantum Astrophysics",
            "comment": "Autonomous analytical documentary series on frontier science, quantum physics, and advanced technology.",
        },
        "color_curves": "eq=contrast=1.08:saturation=1.14:gamma=0.95,colorbalance=bs=0.06:ms=0.02:rs=-0.02",
        "badge_text": "⚛ QUANTUM LAB",
        "badge_border": "#00E5FF",
        "badge_bg": "#050B14",
        "thumb_font": "Rajdhani",
        "thumb_color1": "#FFFFFF",
        "thumb_color2": "#00E5FF",
        "thumb_border": "#050510",
    },
    "nature": {
        "channel_id": "ch2",
        "name": "Nature & Extreme Biology",
        "gemini_voice": "Kore",
        "kokoro_voice": "af_heart",
        "edge_voice": "en-US-AvaNeural",
        "cadence_speed": 0.98,
        "vocal_tone": "deep_curiosity",
        "persona_desc": "wonder, rhythmic cadence, 0.98x",
        "subtitle_fonts": ["Komika Axis", "Gilroy", "Montserrat", "Bebas Neue"],
        "c_base": "&H00F0FFF0&",          # Base: Honeydew Soft Organic White (#F0FFF0)
        "c_active": "&H0066FF00&",        # Active: Bioluminescent Lime (#00FF66)
        "c_power": "&H0000E6FF&",         # Power Accent: Sun Gold
        "outline_color": "&H00102005&",   # Outline: 8px #052010 (abyssal black-green)
        "shadow_color": "&H80081002&",    # Shadow: 3px
        "outline_w": 8,
        "shadow_d": 3,
        "blur": 0,
        "margin_v": 440,
        "procedural_chords": [
            [("E", "min"), ("G", "maj"), ("D", "maj"), ("C", "maj")],
            [("A", "min"), ("C", "maj"), ("G", "maj"), ("F", "maj")],
            [("D", "min"), ("A#", "maj"), ("F", "maj"), ("C", "maj")],
        ],
        "music_bpm": 92,
        "foley_type": "organic_nature",
        "ducking": {
            "attack": 40,
            "release": 350,
            "ratio": 2.8,
            "threshold": 0.09,
            "music_vol": 0.26,
            "sfx_vol": 0.25,
        },
        "container_metadata": {
            "artist": "BioSphere Explorations / Wild Earth Media",
            "genre": "Nature & Wildlife / Extreme Biology",
            "comment": "Documentary expedition exploring abyssal fauna, evolutionary adaptations, and planetary ecosystems.",
        },
        "color_curves": "eq=contrast=1.05:saturation=1.18:gamma=0.98,colorbalance=gs=0.05:gh=0.03:rh=0.02:bh=-0.03",
        "badge_text": "🌿 EXTREME NATURE",
        "badge_border": "#00FF66",
        "badge_bg": "#041408",
        "thumb_font": "Komika Axis",
        "thumb_color1": "#F0FFF0",
        "thumb_color2": "#00FF66",
        "thumb_border": "#052010",
    },
    "history": {
        "channel_id": "ch3",
        "name": "History & Warfare Tactics",
        "gemini_voice": "Charon",
        "kokoro_voice": "am_michael",
        "edge_voice": "en-US-ChristopherNeural",
        "cadence_speed": 0.96,
        "vocal_tone": "dark_revelation",
        "persona_desc": "grave, baritone historical storyteller, 0.96x",
        "subtitle_fonts": ["Cinzel", "TheBoldFont", "Bebas Neue"],
        "c_base": "&H00C7E8F5&",          # Base: Antique Parchment (#F5E8C7)
        "c_active": "&H0000D7FF&",        # Active: Imperial Gold (#FFD700)
        "c_power": "&H003333CC&",         # Power Accent: Imperial Crimson
        "outline_color": "&H00000A1A&",   # Outline: 9px #1A0A00 (bronze mahogany)
        "shadow_color": "&H8000050D&",    # Shadow: 4px
        "outline_w": 9,
        "shadow_d": 4,
        "blur": 2,
        "margin_v": 440,
        "procedural_chords": [
            [("A", "min"), ("D", "min"), ("E", "maj"), ("A", "min")],
            [("D", "min"), ("G", "min"), ("A", "maj"), ("D", "min")],
            [("E", "min"), ("B", "min"), ("C", "maj"), ("B", "maj")],
        ],
        "music_bpm": 80,
        "foley_type": "historical_warfare",
        "ducking": {
            "attack": 20,
            "release": 300,
            "ratio": 3.8,
            "threshold": 0.08,
            "music_vol": 0.24,
            "sfx_vol": 0.29,
        },
        "container_metadata": {
            "artist": "Chronos Archive / Historical Warfare Documentaries",
            "genre": "History & Military Strategy / Tactical Chronicles",
            "comment": "Declassified tactical warfare chronicles, ancient siege mechanics, and empire collapse records.",
        },
        "color_curves": "eq=contrast=1.10:saturation=0.95:gamma=0.93,colorbalance=rs=0.05:rh=0.06:gh=0.02:bs=-0.04:bh=-0.06",
        "badge_text": "⚔ DECLASSIFIED ARCHIVE",
        "badge_border": "#FFD700",
        "badge_bg": "#1A0800",
        "thumb_font": "Cinzel",
        "thumb_color1": "#F5E8C7",
        "thumb_color2": "#FFD700",
        "thumb_border": "#1A0A00",
    },
    "mystery": {
        "channel_id": "ch4",
        "name": "Mysteries & Unexplained",
        "gemini_voice": "Puck",
        "kokoro_voice": "am_fenrir",
        "edge_voice": "en-US-EricNeural",
        "cadence_speed": 1.00,
        "vocal_tone": "suspenseful_mystery",
        "persona_desc": "inquisitive, suspenseful, 1.00x",
        "subtitle_fonts": ["Montserrat Black", "Montserrat", "Archivo Black", "Bebas Neue"],
        "c_base": "&H00E0E0E0&",          # Base: Spectral Silver (#E0E0E0)
        "c_active": "&H0000FFDF&",        # Active: Acid Yellow (#DFFF00)
        "c_power": "&H00FF00B8&",         # Power Accent: Neon Violet
        "outline_color": "&H0014000B&",   # Outline: 10px #0B0014 (obsidian violet)
        "shadow_color": "&H6054003B&",    # Shadow: 4px Violet Drop Shadow (#3B0054)
        "outline_w": 10,
        "shadow_d": 4,
        "blur": 1,
        "margin_v": 440,
        "procedural_chords": [
            [("B", "min"), ("F", "min"), ("G", "maj"), ("C#", "min")],
            [("C", "min"), ("F#", "dim"), ("G#", "maj"), ("D", "min")],
            [("E", "min"), ("A#", "dim"), ("B", "min"), ("F", "maj")],
        ],
        "music_bpm": 104,
        "foley_type": "mystery_eerie",
        "ducking": {
            "attack": 30,
            "release": 400,
            "ratio": 3.0,
            "threshold": 0.10,
            "music_vol": 0.28,
            "sfx_vol": 0.26,
        },
        "container_metadata": {
            "artist": "Enigma Files / Anomalies & Unexplained",
            "genre": "Mystery & Investigation / Archaeological Paradoxes",
            "comment": "Declassified investigations into archaeological enigmas, geological anomalies, and unexplained paradoxes.",
        },
        "color_curves": "eq=contrast=1.12:saturation=0.92:gamma=0.90,colorbalance=bs=0.07:ms=-0.03:rs=-0.04:rh=0.03:bh=0.04,vignette=angle=0.48",
        "badge_text": "👁 UNEXPLAINED FILE",
        "badge_border": "#DFFF00",
        "badge_bg": "#0B0014",
        "thumb_font": "Montserrat Black",
        "thumb_color1": "#E0E0E0",
        "thumb_color2": "#DFFF00",
        "thumb_border": "#0B0014",
    },
    "engineering": {
        "channel_id": "ch5",
        "name": "Megaprojects & Engineering",
        "gemini_voice": "Orus",
        "kokoro_voice": "am_puck",
        "edge_voice": "en-US-BrianNeural",
        "cadence_speed": 1.04,
        "vocal_tone": "bold_authority",
        "persona_desc": "resonant, punchy industrial, 1.04x",
        "subtitle_fonts": ["Barlow Condensed", "Bebas Neue", "Anton"],
        "c_base": "&H00FFFFFF&",          # Base: Blueprint Titanium White (#FFFFFF)
        "c_active": "&H000055FF&",        # Active: Safety Orange (#FF5500)
        "c_power": "&H0000CCFF&",         # Power Accent: Hazard Yellow
        "outline_color": "&H00241E1A&",   # Outline: 9px #1A1E24 (machined dark slate)
        "shadow_color": "&H80120F0D&",    # Shadow: 3px Machine Slate Shadow
        "outline_w": 9,
        "shadow_d": 3,
        "blur": 0,
        "margin_v": 440,
        "procedural_chords": [
            [("C", "min"), ("D#", "maj"), ("F", "maj"), ("G", "min")],
            [("D", "min"), ("F", "maj"), ("G", "maj"), ("A", "min")],
            [("G", "min"), ("A#", "maj"), ("C", "maj"), ("D", "min")],
        ],
        "music_bpm": 130,
        "foley_type": "industrial_machinery",
        "ducking": {
            "attack": 12,
            "release": 150,
            "ratio": 4.5,
            "threshold": 0.06,
            "music_vol": 0.23,
            "sfx_vol": 0.32,
        },
        "container_metadata": {
            "artist": "Apex Megaprojects / Heavy Industrial Engineering",
            "genre": "Civil Engineering & Heavy Machinery / Megastructures",
            "comment": "Documenting extreme infrastructure, tunnel boring breakthroughs, and colossal machines.",
        },
        "color_curves": "eq=contrast=1.12:saturation=1.16:gamma=0.94,colorbalance=rs=0.02:rh=0.05:gh=0.02:bs=0.04:bh=-0.03",
        "badge_text": "⚡ MEGA PROJECT",
        "badge_border": "#FF5500",
        "badge_bg": "#101418",
        "thumb_font": "Barlow Condensed",
        "thumb_color1": "#FFFFFF",
        "thumb_color2": "#FF5500",
        "thumb_border": "#1A1E24",
    },
}

def get_channel_profile(niche: str = None) -> dict:
    if not niche:
        niche = os.environ.get("CHANNEL_NICHE", CHANNEL_NICHE).lower()
    return FLEET_NICHE_PROFILES.get(niche, FLEET_NICHE_PROFILES.get("science", {}))

# Niche-adaptive active voice settings
_curr_profile = get_channel_profile()
DEFAULT_GEMINI_VOICE = _curr_profile.get("gemini_voice", "Fenrir")
DEFAULT_EDGE_VOICE = _curr_profile.get("edge_voice", "en-US-AndrewNeural")
DEFAULT_KOKORO_VOICE = _curr_profile.get("kokoro_voice", "am_adam")
VOICE_PITCH = 0.0
VOICE_RATE = _curr_profile.get("cadence_speed", 1.02)

