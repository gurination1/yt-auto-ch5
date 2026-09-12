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
GEMINI_FLASH        = "gemini-3.6-flash"
GEMINI_FLASH_BACKUP = "gemini-3.5-flash-lite"
GEMINI_PRO          = "gemini-3.6-flash"
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

# ── Channel Boundary & Topic Isolation (Channel 5: Mind Here Business - Business, Global Trade & Market Secrets) ──
CHANNEL_NICHE = os.environ.get("CHANNEL_NICHE", "business")

CHANNEL_BOUNDARY = {
    "channel_id": "ch5",
    "name": "Channel 5: Mind Here Business (Business, Global Trade & Market Secrets)",
    "niche_description": "High-stakes corporate maneuvers, global supply chain chokepoints, dark commodity cartels, pricing psychology, market anomalies, and secret economic machinery behind billion-dollar industries.",
    "allowed_subclusters": [
        "global supply chain chokepoints and maritime trade bottlenecks: Suez Canal economics, Malacca Straits, ASML lithography monopoly, and semiconductor foundries",
        "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology",
        "commodity monopolies and dark resource syndicates: global sand mining cartels, vanilla syndicate wars, cobalt supply chains, and lithium reserves",
        "industrial alchemy and unexpected corporate pivots: how jet engine manufacturers make zero profit on engines and billions on hourly flight hour contracts, and e-waste gold recovery",
        "artificial scarcity and luxury cartel mechanics: De Beers diamond supply vaults, Hermès quota systems, Swiss watch waitlists, and designer fashion inventory destruction"
    ],
    "strict_negative_constraints": [
        "NO space astrophysics, astronomy, cosmology, telescopes, black holes, or rocket engines.",
        "NO wildlife biology, animal adaptations, zoology, marine predators, or nature documentaries.",
        "NO ancient Roman legions, medieval swords, catapults, or ancient battlefield sieges.",
        "NO heavy civil construction specs, crane lift charts, or TBM cutterhead engineering.",
        "NO crypto shitcoin shilling, day-trading chart analysis, forex signals, or get-rich-quick motivational hustle advice."
    ],
    "negative_keywords": [
        "astronomy", "astrophysics", "telescope", "james webb", "black hole", "cosmology", "galaxy", "supernova",
        "wildlife documentary", "zoology", "apex predator", "venomous snake", "insect swarm", "mammal species", "deep sea creature",
        "roman legion", "gladiator battle", "trebuchet", "catapult", "medieval battle", "ancient warfare",
        "tunnel boring machine", "tbm cutterhead", "bridge pier", "crawler crane", "concrete gravity dam",
        "crypto token", "shiba inu", "memecoin", "day trading chart", "candlestick pattern", "forex signals", "get rich quick", "hustle mindset"
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
YT_CATEGORY_SCIENCE   = "27"
YT_CATEGORY_DEFAULT   = "27"
NASA_BROLL_ENABLED    = False

RICH_FALLBACK_TOPICS = [
    {
        "topic": "The Costco Hot Dog Paradox: Why Costco's founder threatened to murder the CEO if he raised the $1.50 hot dog price, and how it anchors $200B in sales",
        "short_hook": "Why will Costco fire any executive who touches the $1.50 hot dog?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "ASML's Extreme UV Monopoly: How a single Dutch company controls 100% of the world's extreme UV chipmaking machines and holds the tech economy hostage",
        "short_hook": "One Dutch company holds a monopoly on every advanced computer chip on Earth.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "global supply chain chokepoints and maritime trade bottlenecks: Suez Canal economics, Malacca Straits, ASML lithography monopoly, and semiconductor foundries"
    },
    {
        "topic": "The Global Sand Mafia: How illegal syndicates and armed cartels steal millions of tons of beach and river sand to feed the concrete construction boom",
        "short_hook": "Why are armed syndicates fighting deadly cartel wars over river sand?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "commodity monopolies and dark resource syndicates: global sand mining cartels, vanilla syndicate wars, cobalt supply chains, and lithium reserves"
    },
    {
        "topic": "Rolls-Royce Power-by-the-Hour: Why jet engine manufacturers sell multi-million-dollar engines at a loss and print billions renting uptime by the minute",
        "short_hook": "Why do jet engine makers sell their engines at a massive loss?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "industrial alchemy and unexpected corporate pivots: how jet engine manufacturers make zero profit on engines and billions on hourly flight hour contracts, and e-waste gold recovery"
    },
    {
        "topic": "The De Beers Diamond Illusion: How an offshore cartel invented the engagement ring tradition out of thin air and artificially stockpiled diamonds to inflate prices",
        "short_hook": "How a cartel tricked the world into believing clear carbon rocks are rare and valuable.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "artificial scarcity and luxury cartel mechanics: De Beers diamond supply vaults, Hermès quota systems, Swiss watch waitlists, and designer fashion inventory destruction"
    },
    {
        "topic": "The Suez Canal Chokepoint: How a single stuck container ship froze $9.6 billion of global trade every day and triggered a worldwide inflation shockwave",
        "short_hook": "How one stuck boat paralyzed 10 billion dollars of global trade every single day.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "global supply chain chokepoints and maritime trade bottlenecks: Suez Canal economics, Malacca Straits, ASML lithography monopoly, and semiconductor foundries"
    },
    {
        "topic": "Cinema Popcorn Economics: Why movie theaters are actually popcorn concessions that show Hollywood movies as an excuse to sell 1,200% markup snacks",
        "short_hook": "Movie theaters don't make money on tickets. They make it on 1,200% popcorn markup.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "The Madagascar Vanilla Syndicate: Why natural vanilla beans are worth more by weight than silver and protected by armed jungle militias",
        "short_hook": "Why is natural vanilla more valuable by weight than solid silver?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "commodity monopolies and dark resource syndicates: global sand mining cartels, vanilla syndicate wars, cobalt supply chains, and lithium reserves"
    },
    {
        "topic": "The Hermès Birkin Quota Game: How a luxury brand uses forced artificial scarcity and purchase histories to make handbags appreciate faster than the stock market",
        "short_hook": "Why having $30,000 cash still won't let you buy a Birkin bag from Hermès.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "artificial scarcity and luxury cartel mechanics: De Beers diamond supply vaults, Hermès quota systems, Swiss watch waitlists, and designer fashion inventory destruction"
    },
    {
        "topic": "The Gillette Razor and Blades Model: How industrial consumables trap millions of consumers into high-margin refill subscriptions for decades",
        "short_hook": "The genius corporate trap that gets you to pay for the rest of your life.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "The Strait of Malacca Bottleneck: Why 25% of all global traded oil passes through a 1.7-mile maritime corridor and what happens if it shuts down",
        "short_hook": "A 1.7-mile stretch of water controls 25% of all oil shipped on planet Earth.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "global supply chain chokepoints and maritime trade bottlenecks: Suez Canal economics, Malacca Straits, ASML lithography monopoly, and semiconductor foundries"
    },
    {
        "topic": "E-Waste Urban Mining: Why extracting gold and palladium from a ton of discarded smartphones yields 100 times more precious metal than mining raw gold ore",
        "short_hook": "A ton of old smartphones holds 100 times more gold than a ton of gold ore.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "industrial alchemy and unexpected corporate pivots: how jet engine manufacturers make zero profit on engines and billions on hourly flight hour contracts, and e-waste gold recovery"
    },
    {
        "topic": "Surge Pricing & Battery Drain Algorithms: How travel apps and rideshares detect your remaining battery percentage and demand velocity to secretly inflate prices",
        "short_hook": "Does your phone's dying battery actually make your Uber ride more expensive?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "The Gray Market Rolex Syndicate: How authorized dealers secretly funnel brand-new luxury watches to gray-market flippers for double retail price",
        "short_hook": "Why your local luxury watch dealer is secretly selling watches to gray market flippers.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "artificial scarcity and luxury cartel mechanics: De Beers diamond supply vaults, Hermès quota systems, Swiss watch waitlists, and designer fashion inventory destruction"
    },
    {
        "topic": "The Lithium Triangle Geopolitics: How Chile, Bolivia, and Argentina control 50% of the world's battery reserves and play superpowers against each other",
        "short_hook": "Three countries in South America control 50% of the world's battery future.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "commodity monopolies and dark resource syndicates: global sand mining cartels, vanilla syndicate wars, cobalt supply chains, and lithium reserves"
    },
    {
        "topic": "The Gruen Transfer in Supermarket Architecture: Why grocery stores place milk in the furthest back corner and pump bakery scents to force impulse purchases",
        "short_hook": "Why is milk always placed at the furthest possible corner of every grocery store?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "The DRC Cobalt Chokepoint: How 70% of the global cobalt supply needed for every electric vehicle and smartphone originates from a single mining province",
        "short_hook": "70% of the world's smartphone batteries depend on a single country's mines.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "commodity monopolies and dark resource syndicates: global sand mining cartels, vanilla syndicate wars, cobalt supply chains, and lithium reserves"
    },
    {
        "topic": "The SaaS Subscription Shift: How software companies abandoned $50 lifetime licenses for recurring monthly fees and multiplied corporate valuations tenfold",
        "short_hook": "Why did software companies kill lifetime licenses to force monthly rent on users?",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "Haber-Bosch and Fertilizer Economics: How natural gas feedstock produces global ammonia fertilizer that feeds 50% of the human population",
        "short_hook": "Half of the world's food supply depends on this single chemical trade route.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "commodity monopolies and dark resource syndicates: global sand mining cartels, vanilla syndicate wars, cobalt supply chains, and lithium reserves"
    },
    {
        "topic": "Loss-Leader Milk Wars: How mega-supermarkets weaponize gallon milk prices below wholesale cost to bankrupt independent grocers",
        "short_hook": "Supermarkets sell gallon milk at a guaranteed loss just to crush local competitors.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "The Intermodal Shipping Container: How a standardized corrugated steel box invented by Malcolm McLean dropped freight transport costs by 99%",
        "short_hook": "How this plain steel box dropped the cost of global trade by 99%.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "global supply chain chokepoints and maritime trade bottlenecks: Suez Canal economics, Malacca Straits, ASML lithography monopoly, and semiconductor foundries"
    },
    {
        "topic": "Luxury Inventory Burning: Why Burberry and Cartier destroyed hundreds of millions in pristine unsold coats and watches rather than discount them",
        "short_hook": "Why luxury fashion brands set fire to millions of dollars of unsold clothes.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "artificial scarcity and luxury cartel mechanics: De Beers diamond supply vaults, Hermès quota systems, Swiss watch waitlists, and designer fashion inventory destruction"
    },
    {
        "topic": "The Global Helium Crisis: Why medical MRI machines and semiconductor cleanrooms are scrambling over an irreplaceable non-renewable underground gas",
        "short_hook": "Why the world is quietly running out of the gas that cools MRI machines.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "commodity monopolies and dark resource syndicates: global sand mining cartels, vanilla syndicate wars, cobalt supply chains, and lithium reserves"
    },
    {
        "topic": "Casino Floor Psychological Engineering: Why casinos eliminate windows, remove all clocks, and curve carpet pathways to distort time and risk perception",
        "short_hook": "The calculated psychological tricks casinos use to make you lose track of time.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
    },
    {
        "topic": "Pharmaceutical Patent Thickets: How drug corporations file hundreds of minor secondary patents to delay generic life-saving medicine competition for 30 years",
        "short_hook": "How drug companies build patent fortresses to block cheap medicine for 30 years.",
        "hook_type": "curiosity_gap",
        "for_format": "both",
        "subcluster": "corporate pricing psychology and hidden profit engines: Costco hot dog loss leader economics, cinema concession profit margins, airline dynamic seat tiering, and supermarket layout psychology"
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
        "color_curves": "eq=contrast=1.08:saturation=1.14:gamma=0.95,colorbalance=bs=0.06:bm=0.02:rs=-0.02",
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
        "color_curves": "eq=contrast=1.12:saturation=0.92:gamma=0.90,colorbalance=bs=0.07:bm=-0.03:rs=-0.04:rh=0.03:bh=0.04",
        "badge_text": "👁 UNEXPLAINED FILE",
        "badge_border": "#DFFF00",
        "badge_bg": "#0B0014",
        "thumb_font": "Montserrat Black",
        "thumb_color1": "#E0E0E0",
        "thumb_color2": "#DFFF00",
        "thumb_border": "#0B0014",
    },
    "engineering": {
        "channel_id": "ch4",
        "name": "Marvel Engeneering (Engineering Marvels & How It Works)",
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
            "artist": "Marvel Engeneering / Engineering Marvels & How It Works",
            "genre": "Engineering & Technology / Colossal Machines & Extreme Feats",
            "comment": "Documenting colossal machines, extreme kinetic mechanisms, and how impossible engineering feats work.",
        },
        "color_curves": "eq=contrast=1.12:saturation=1.16:gamma=0.94,colorbalance=rs=0.02:rh=0.05:gh=0.02:bs=0.04:bh=-0.03",
        "badge_text": "⚙ ENGINEERING MARVEL",
        "badge_border": "#FF5500",
        "badge_bg": "#101418",
        "thumb_font": "Barlow Condensed",
        "thumb_color1": "#FFFFFF",
        "thumb_color2": "#FF5500",
        "thumb_border": "#1A1E24",
    },
    "business": {
        "channel_id": "ch5",
        "name": "Mind Here Business (Business, Global Trade & Market Secrets)",
        "gemini_voice": "Charon",
        "kokoro_voice": "am_michael",
        "edge_voice": "en-US-ChristopherNeural",
        "cadence_speed": 1.02,
        "vocal_tone": "bold_authority",
        "persona_desc": "authoritative financial & trade investigator, 1.02x",
        "subtitle_fonts": ["Montserrat", "Montserrat Black", "Bebas Neue"],
        "c_base": "&H00FFFFFF&",          # Base: Pure Crisp White (#FFFFFF)
        "c_active": "&H00A3E500&",        # Active: Wealth Emerald (#00E5A3)
        "c_power": "&H0000D7FF&",         # Power Accent: Gold (#FFD700)
        "outline_color": "&H000A0805&",   # Outline: 9px #05080A (obsidian navy)
        "shadow_color": "&H80000000&",    # Shadow: 3px
        "outline_w": 9,
        "shadow_d": 3,
        "blur": 1,
        "margin_v": 440,
        "procedural_chords": [
            [("C", "min"), ("Ab", "maj"), ("Eb", "maj"), ("Bb", "maj")],
            [("D", "min"), ("Bb", "maj"), ("F", "maj"), ("C", "maj")],
            [("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")],
        ],
        "music_bpm": 112,
        "foley_type": "digital_tech",
        "ducking": {
            "attack": 20,
            "release": 250,
            "ratio": 3.8,
            "threshold": 0.08,
            "music_vol": 0.22,
            "sfx_vol": 0.28,
        },
        "container_metadata": {
            "artist": "Mind Here Business / Global Trade & Corporate Investigations",
            "genre": "Business & Economics / Global Trade & Market Secrets",
            "comment": "Investigative documentary series on global supply chain chokepoints, corporate monopolies, and market secrets.",
        },
        "color_curves": "eq=contrast=1.12:saturation=1.10:gamma=0.95,colorbalance=rs=0.03:gs=0.04:bs=-0.02",
        "badge_text": "$ TRADE SECRETS",
        "badge_border": "#00E5A3",
        "badge_bg": "#05120C",
        "thumb_font": "Montserrat",
        "thumb_color1": "#FFFFFF",
        "thumb_color2": "#00E5A3",
        "thumb_border": "#05080A",
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

