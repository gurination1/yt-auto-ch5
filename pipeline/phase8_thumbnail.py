import os
import random
import subprocess
import requests
import urllib.parse
import re

def _extract_punchy_hook(topic: str, title: str) -> tuple[str, str]:
    """Generate or extract a 2-4 word ultra-punchy ALL CAPS hook for high CTR."""
    meta_words = {"THUMBNAIL", "TEXT", "THUMBNAILTEXT", "HOOK", "TITLE", "JSON", "RESPONSE"}
    candidate = title.strip() or topic.strip()
    clean_candidate = re.sub(r'[^A-Za-z0-9\s]', ' ', candidate).strip()
    cand_words = [w.upper() for w in clean_candidate.split() if w.upper() not in meta_words]
    if 2 <= len(cand_words) <= 4:
        hook_words = cand_words
    else:
        hook_words = []
        try:
            from pipeline.gemini import GeminiClient, _robust_json_loads
            client = GeminiClient()
            prompt = (
                f"Topic: '{topic}' | Title: '{title}'\n"
                f"Generate a 2 to 4 word ultra-punchy YouTube thumbnail text hook. "
                f"ALL CAPS, 2-4 words only, high curiosity. "
                f"Return JSON: {{\"hook\": \"OCEANS OF DIAMONDS\"}}"
            )
            res = client.generate_text(prompt, max_tokens=60).strip()
            data = _robust_json_loads(res)
            hook_str = data.get("hook", "")
            clean = re.sub(r'[^A-Za-z0-9\s]', ' ', hook_str).strip()
            words = [w.upper() for w in clean.split() if w.upper() not in meta_words]
            if 2 <= len(words) <= 4:
                hook_words = words
        except Exception as e:
            print(f"[Thumbnail] Gemini hook generation fallback: {e}")

    if not hook_words:
        stop = {
            "breakthrough", "logic", "superposition", "fundamental", "discovery", "the", "and", "for", "with",
            "how", "why", "what", "in", "of", "to", "a", "an", "is", "by", "that", "this", "inside", "overturns"
        }
        raw_words = [w.upper() for w in re.findall(r'[A-Za-z0-9]+', title or topic) if len(w) > 2 and w.lower() not in stop and w.upper() not in meta_words]
        hook_words = raw_words[:3] if raw_words else ["DISCOVERY", "UNLOCKED"]

    if len(hook_words) == 1:
        return hook_words[0], ""
    elif len(hook_words) == 2:
        return hook_words[0], hook_words[1]
    elif len(hook_words) == 3:
        return hook_words[0], " ".join(hook_words[1:])
    else:
        mid = len(hook_words) // 2
        return " ".join(hook_words[:mid]), " ".join(hook_words[mid:])

def _generate_ai_background(topic: str, niche: str = "general") -> str | None:
    """Generates a high-contrast 16:9 cinematic background image via Pollinations AI (Flux)."""
    niche_styles = {
        "science": "futuristic quantum laboratory glowing energy core particle physics neon blue cyan amber dramatic lighting 8k cinematic",
        "nature": "deep ocean abyssal bioluminescent glowing alien sea creature abyss dark water ultra detailed 8k cinematic",
        "history": "ancient battle fortress Roman legion siege warfare cinematic dust volumetric lighting 8k photorealistic",
        "mystery": "unexplained ancient archaeological megalith dark mysterious atmosphere glowing runes cinematic 8k",
        "engineering": "colossal megaproject subsea tunnel massive industrial mega excavator hydraulic machinery 8k cinematic",
        "general": "cinematic 8k high contrast dramatic lighting photorealistic 16:9"
    }
    style = niche_styles.get(niche, niche_styles["general"])
    prompt = f"{topic}, {style}, 16:9, Unreal Engine 5 render, award winning photography, no text, no words, no letters"
    
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&model=flux&nologo=true&seed={seed}"
    
    temp_bg = "output/thumb_bg.jpg"
    os.makedirs("output", exist_ok=True)
    try:
        r = requests.get(url, timeout=25)
        if r.status_code == 200 and len(r.content) > 10000:
            with open(temp_bg, "wb") as f:
                f.write(r.content)
            print("[Thumbnail] Generated 16:9 AI background via Pollinations AI (Flux)!")
            return temp_bg
    except Exception as e:
        print(f"[Thumbnail] AI background generator error: {e}")
    return None

def generate_thumbnail(final_video_path: str, thumbnail_text: str, topic_prompt: str = "", channel: str = "general") -> str:
    print(f"[Thumbnail] Generating viral thumbnail for topic='{topic_prompt}' | title='{thumbnail_text}'...")
    os.makedirs("output", exist_ok=True)
    thumbnail_path = "output/thumbnail.jpg"

    # 1. Generate punchy 2-4 word hook (Line 1 + Line 2)
    line1, line2 = _extract_punchy_hook(topic_prompt, thumbnail_text)
    print(f"[Thumbnail] Punchy Hook: Line 1: '{line1}' | Line 2: '{line2}'")

    # 2. Generate 16:9 background
    bg_file = _generate_ai_background(topic_prompt or thumbnail_text, niche=channel)
    if not bg_file or not os.path.exists(bg_file):
        # Fallback: extract best frame from video
        bg_file = "output/hook_frame.jpg"
        print("[Thumbnail] Extracting video frame for thumbnail background...")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", final_video_path, "-vf", "thumbnail=n=300,scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", "-frames:v", "1", "-q:v", "2", bg_file],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            cmd_black = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x0d1117:s=1280x720:d=1", "-vframes", "1", bg_file]
            subprocess.run(cmd_black, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3. Dynamic Font Size Calculation
    max_len = max(len(line1), len(line2))
    fontsize = 135 if max_len <= 8 else 115 if max_len <= 12 else 95

    # 4. Color Palette
    color1 = "#FFFFFF" # Crisp white
    color2 = "#FFE500" # Electric yellow

    filter_parts = [
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.20:t=fill"
    ]

    if line2:
        y1 = f"(h/2)-{int(fontsize*0.95)}"
        y2 = f"(h/2)+{int(fontsize*0.15)}"
        filter_parts.append(
            f"drawtext=text='{line1}':font='Bebas Neue':fontsize={fontsize}:"
            f"fontcolor='{color1}':borderw=10:bordercolor=black:shadowcolor=black@0.95:shadowx=8:shadowy=8:x=(w-text_w)/2:y={y1}"
        )
        filter_parts.append(
            f"drawtext=text='{line2}':font='Bebas Neue':fontsize={fontsize}:"
            f"fontcolor='{color2}':borderw=10:bordercolor=black:shadowcolor=black@0.95:shadowx=8:shadowy=8:x=(w-text_w)/2:y={y2}"
        )
    else:
        filter_parts.append(
            f"drawtext=text='{line1}':font='Bebas Neue':fontsize={fontsize+20}:"
            f"fontcolor='{color2}':borderw=10:bordercolor=black:shadowcolor=black@0.95:shadowx=8:shadowy=8:x=(w-text_w)/2:y=(h-text_h)/2"
        )

    vf = ",".join(filter_parts)
    cmd = ["ffmpeg", "-y", "-i", bg_file, "-vf", vf, "-q:v", "2", thumbnail_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("[Thumbnail] Bebas Neue font fallback to DejaVu Sans Bold...")
        vf_fb = vf.replace("font='Bebas Neue'", "font='DejaVu Sans Bold'")
        cmd_fb = ["ffmpeg", "-y", "-i", bg_file, "-vf", vf_fb, "-q:v", "2", thumbnail_path]
        subprocess.run(cmd_fb, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[Thumbnail] Viral thumbnail successfully generated: {thumbnail_path} ({os.path.getsize(thumbnail_path)} bytes)")
    return thumbnail_path
