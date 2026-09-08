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

GEMINI_VOICES    = ["Fenrir", "Puck", "Charon", "Orus", "Kore"]
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

DEFAULT_GEMINI_VOICE = "Fenrir"
DEFAULT_KOKORO_VOICE = "am_adam"
VOICE_PITCH = 0.0
VOICE_RATE = 1.02
