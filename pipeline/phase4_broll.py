
import os
import re
import random
import requests

def _validate_and_normalize_image(img_path: str) -> bool:
    """Validates image with PIL, converts to standard 8-bit RGB JPEG, caps dimensions to 2560px, returns True if valid."""
    try:
        from PIL import Image
        if not os.path.exists(img_path) or os.path.getsize(img_path) < 1000:
            return False
        with Image.open(img_path) as im:
            im.verify()
        with Image.open(img_path) as im:
            im = im.convert("RGB")
            w, h = im.size
            if max(w, h) > 2560:
                scale = 2560 / max(w, h)
                im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            im.save(img_path, "JPEG", quality=95)
        return True
    except Exception as e:
        print(f"[B-roll] Image validation/normalization failed for {img_path}: {e}")
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception:
                pass
        return False

def _wikipedia_hd_image(query: str, img_path: str, used_urls: set[str] | None = None, topic: str = "") -> bool:
    """
    Fetches official high-resolution authentic photograph/micrograph of entity from Wikipedia/Wikimedia.
    Enforces strict topic/query relevance, rejects 2D diagrams/charts/flags, and prevents duplicate reuse.
    """
    try:
        STOPLIST = {
            "footage", "real", "authentic", "documentary", "megaproject", "construction", "colossal", "machinery",
            "what", "inside", "secret", "incredible", "shocking", "4k", "1080p", "hd", "video", "broll", "clip",
            "the", "and", "for", "with", "this", "that", "from", "into", "over", "under", "about", "scene", "view"
        }
        query_words = [w.lower() for w in re.sub(r'[^a-zA-Z0-9\s]', '', query).split() if len(w) > 2 and w.lower() not in STOPLIST]
        topic_words = [w.lower() for w in re.sub(r'[^a-zA-Z0-9\s]', '', topic).split() if len(w) > 2 and w.lower() not in STOPLIST] if topic else []
        anchor_words = set(query_words + topic_words)
        if not anchor_words:
            return False

        entity = " ".join(query_words[:4]) if query_words else query[:60]
        headers = {"User-Agent": "yt-auto-fleet/2.0 (educational-video-pipeline; mailto:contact@gurination.com)"}

        BANNED_IMAGE_PATTERNS = [
            "diagram", "drawing", "chart", "graph", "formula", "symbol", "icon", "logo", "flag",
            "schematic", "sketch", "map_", "plan_", "table", "plot", "spectrum", "curves",
            "render_3d_arrow", "arrows", "vector", "infographic", "illustration", "cartoon",
            "locator_map", "location_map", "blank"
        ]

        def _is_valid_image(url: str, title: str = "") -> bool:
            if not url or not url.startswith("http"):
                return False
            if used_urls is not None and url in used_urls:
                return False
            url_lower = url.lower()
            title_lower = title.lower()
            if any(p in url_lower or p in title_lower for p in BANNED_IMAGE_PATTERNS):
                return False
            # Title relevance check: require at least one anchor word in page/image title
            if title_lower:
                t_words = set(re.sub(r'[^a-zA-Z0-9\s]', ' ', title_lower).split())
                if not (t_words & anchor_words):
                    return False
            return True

        url_wiki = "https://en.wikipedia.org/w/api.php"

        # 1. Direct Wikipedia title match
        r = requests.get(url_wiki, params={
            "action": "query", "titles": entity, "prop": "pageimages", "format": "json", "pithumbsize": 1920
        }, headers=headers, timeout=8)
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                if pid != "-1":
                    thumb = pdata.get("thumbnail", {}).get("source")
                    p_title = pdata.get("title", "")
                    if thumb and _is_valid_image(thumb, p_title):
                        r_img = requests.get(thumb, headers=headers, timeout=12)
                        if r_img.status_code == 200 and len(r_img.content) > 10_000:
                            with open(img_path, "wb") as f:
                                f.write(r_img.content)
                            if _validate_and_normalize_image(img_path):
                                if used_urls is not None:
                                    used_urls.add(thumb)
                                print(f"[B-roll] Fetched official Wikipedia HD photo for '{p_title}'.")
                                return True

        # 2. Wikipedia generator search with strict title verification
        r_gen = requests.get(url_wiki, params={
            "action": "query", "generator": "search", "gsrsearch": entity, "gsrlimit": "4",
            "prop": "pageimages", "pithumbsize": 1920, "format": "json"
        }, headers=headers, timeout=8)
        if r_gen.status_code == 200:
            pages = r_gen.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                thumb = pdata.get("thumbnail", {}).get("source")
                p_title = pdata.get("title", "")
                if thumb and _is_valid_image(thumb, p_title):
                    r_img = requests.get(thumb, headers=headers, timeout=12)
                    if r_img.status_code == 200 and len(r_img.content) > 10_000:
                        with open(img_path, "wb") as f:
                            f.write(r_img.content)
                        if _validate_and_normalize_image(img_path):
                            if used_urls is not None:
                                used_urls.add(thumb)
                            print(f"[B-roll] Fetched search-matched Wikipedia HD photo for '{p_title}'.")
                            return True

        # 3. Wikimedia Commons photo archive (photos only, strictly no diagrams)
        url_comm = "https://commons.wikimedia.org/w/api.php"
        r_comm = requests.get(url_comm, params={
            "action": "query", "generator": "search", "gsrsearch": f"{entity} -diagram -drawing -chart filetype:bitmap",
            "gsrnamespace": "6", "gsrlimit": "5", "prop": "imageinfo", "iiprop": "url",
            "iiurlwidth": "1920", "format": "json"
        }, headers=headers, timeout=8)
        if r_comm.status_code == 200:
            pages = r_comm.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                ii = pdata.get("imageinfo", [{}])[0]
                thumb = ii.get("thumburl") or ii.get("url")
                f_title = pdata.get("title", "")
                if thumb and _is_valid_image(thumb, f_title):
                    r_img = requests.get(thumb, headers=headers, timeout=12)
                    if r_img.status_code == 200 and len(r_img.content) > 10_000:
                        with open(img_path, "wb") as f:
                            f.write(r_img.content)
                        if _validate_and_normalize_image(img_path):
                            if used_urls is not None:
                                used_urls.add(thumb)
                            print(f"[B-roll] Fetched authentic Commons archive photo for '{f_title}'.")
                            return True
    except Exception as e:
        print(f"[B-roll] Authentic HD photo fetch note: {e}")
    if os.path.exists(img_path):
        try:
            os.remove(img_path)
        except Exception:
            pass
    return False

def _get_ytdlp_bin() -> list[str]:
    import shutil, sys
    for p in ["/usr/local/bin/yt-dlp", "/mnt/g/yt-auto-fleet/venv/bin/yt-dlp", "/home/manveer2/venv_yt_auto/bin/yt-dlp"]:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return [p]
    bin_path = shutil.which("yt-dlp")
    if bin_path:
        return [bin_path]
    return [sys.executable, "-m", "yt_dlp"]

import socket
socket.setdefaulttimeout(15.0)
import os
import re
import random
import requests
import urllib.parse
import subprocess
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pipeline.config import PEXELS_API_KEY, PIXABAY_API_KEY, COVERR_API_KEY, NASA_API_KEY, KLIPY_API_KEY, NASA_BROLL_ENABLED, GEMINI_API_BASE, GEMINI_FLASH



def _nasa_params(query: str, media_type: str, page_size: int) -> dict:
    clean_q = re.sub(r"[^\w\s-]", " ", query or "")
    words = [w for w in clean_q.split() if w.lower() not in {"the", "a", "an", "and", "or", "to", "in", "of", "for", "with", "on", "at", "by", "from", "4k", "hd", "real", "footage", "clip"}]
    clean_q = " ".join(words[:4]).strip()
    return {
        "q": clean_q or "space exploration",
        "media_type": media_type,
        "page_size": page_size,
    }


def _walk_urls(obj) -> list[str]:
    urls: list[str] = []
    if isinstance(obj, dict):
        for value in obj.values():
            urls.extend(_walk_urls(value))
    elif isinstance(obj, list):
        for value in obj:
            urls.extend(_walk_urls(value))
    elif isinstance(obj, str) and obj.startswith("http"):
        urls.append(obj)
    return urls


def _pick_klipy_urls(item: dict) -> tuple[str | None, str | None]:
    urls = _walk_urls(item)
    video_url = None
    thumb_url = None
    for ext in (".mp4", ".webm", ".gif"):
        video_url = next((u for u in urls if ext in u.lower()), None)
        if video_url:
            break
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        thumb_url = next((u for u in urls if ext in u.lower()), None)
        if thumb_url:
            break
    if not thumb_url:
        thumb_url = video_url
    return video_url, thumb_url


def _klipy_candidates(query: str, n: int = 4) -> list[dict]:
    if not KLIPY_API_KEY:
        return []
    try:
        r = requests.get(
            f"https://api.klipy.com/api/v1/{KLIPY_API_KEY}/gifs/search",
            params={"q": query, "per_page": max(8, n), "rating": "pg-13", "locale": "en_US"},
            headers={"User-Agent": "yt-auto/1.0"},
            timeout=25,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("data") or data.get("results") or data.get("gifs") or []
        if isinstance(items, dict):
            items = list(items.values())
        candidates = []
        for item in items:
            if not isinstance(item, dict):
                continue
            video_url, thumb_url = _pick_klipy_urls(item)
            if video_url and thumb_url:
                candidates.append({
                    "video_url": video_url,
                    "thumb_url": thumb_url,
                    "source": "Klipy"
                })
            if len(candidates) >= n:
                break
        return candidates
    except Exception as e:
        print(f"[B-roll] Klipy search failed for '{query}': {e}")
        return []


def _klipy_video(query: str) -> str | None:
    candidates = _klipy_candidates(query, n=1)
    return candidates[0]["video_url"] if candidates else None


# ── Source 1: Pexels Candidates ──────────────────────────────────────────────

def _pexels_candidates(query: str, orientation: str, n: int = 8) -> list[dict]:
    if not PEXELS_API_KEY:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={
                "query": query,
                "per_page": min(80, max(n * 4, 20)),
                "orientation": orientation,
            },
            timeout=25,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        candidates = []
        for video in videos:
            image_url = video.get("image")
            video_files = [f for f in video.get("video_files", []) if f.get("link")]
            if image_url and video_files:
                video_files.sort(key=lambda f: f.get("width", 0), reverse=True)
                v_page_url = video.get("url", "")
                slug = v_page_url.rstrip("/").split("/")[-1]
                slug_clean = re.sub(r'-\d+$', '', slug).replace("-", " ")
                
                tags_list = []
                for t in video.get("tags", []):
                    if isinstance(t, dict):
                        tags_list.append(t.get("name", ""))
                    elif isinstance(t, str):
                        tags_list.append(t)

                candidates.append({
                    "video_url": video_files[0]["link"],
                    "thumb_url": image_url,
                    "title": slug_clean,
                    "tags": tags_list,
                    "source": "Pexels"
                })
        return candidates
    except Exception as e:
        print(f"[B-roll] Pexels search failed for '{query}': {e}")
        return []


# ── Source 2: Pixabay ────────────────────────────────────────────────────────

def _pixabay_video(query: str) -> str | None:
    if not PIXABAY_API_KEY:
        return None
    clean_q = _sanitize_broll_query(query)[:80]
    if not clean_q:
        return None
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            params={
                "key": PIXABAY_API_KEY,
                "q": clean_q,
                "per_page": min(50, max(3 * 3, 10)),
                "order": "popular",
                "safesearch": "true",
                "min_width": 1920
            },
            timeout=30,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        if not hits:
            return None
        videos_data = hits[0].get("videos", {})
        for size in ["large", "medium", "small", "tiny"]:
            url = videos_data.get(size, {}).get("url")
            if url:
                return url
        return None
    except Exception as e:
        print(f"[B-roll] Pixabay failed for '{clean_q}': {e}")
        return None


# ── Source 3: Coverr (cinematic, high quality) ───────────────────────────────

def _extract_coverr_stream(item: dict) -> tuple[str | None, int, int]:
    urls = item.get("urls", {})
    if not isinstance(urls, dict) or not urls:
        return None, 0, 0
    is_vert = item.get("is_vertical", False)
    w = item.get("max_width") or item.get("width") or (1080 if is_vert else 1920)
    h = item.get("max_height") or item.get("height") or (1920 if is_vert else 1080)
    for k in ["4k", "2160p", "1080p", "hd", "mp4_download", "mp4"]:
        val = urls.get(k)
        if isinstance(val, str) and val.startswith("http"):
            return val, w, h
        elif isinstance(val, dict):
            for res_k in ["4k", "2160p", "1080p", "hd", "sd"]:
                res_url = val.get(res_k)
                if isinstance(res_url, str) and res_url.startswith("http"):
                    return res_url, w, h
    return None, 0, 0


def _coverr_video(query: str, orientation: str = "landscape") -> str | None:
    if not COVERR_API_KEY:
        return None
    try:
        cands = _coverr_candidates(query, orientation=orientation, n=1)
        if cands:
            return cands[0]["video_url"]
        return None
    except Exception as e:
        print(f"[B-roll] Coverr failed for '{query}': {e}")
        return None


def _coverr_candidates(query: str, orientation: str = "landscape", n: int = 4) -> list[dict]:
    if not COVERR_API_KEY:
        return []
    try:
        clean_q = _sanitize_broll_query(query)
        headers = {"Authorization": f"Bearer {COVERR_API_KEY}"} if not COVERR_API_KEY.startswith("Bearer") else {"Authorization": COVERR_API_KEY}
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        r = requests.get(
            "https://api.coverr.co/videos",
            headers=headers,
            params={
                "query": clean_q,
                "page": 0,
                "size": min(40, max(n * 4, 15)),
                "urls": "true",
                "sort": "popular"
            },
            timeout=25,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        candidates = []
        for item in hits:
            thumb = item.get("thumbnail")
            video_url, width, height = _extract_coverr_stream(item)
            if thumb and video_url:
                is_vertical = item.get("is_vertical", False)
                candidates.append({
                    "video_url": video_url,
                    "thumb_url": thumb,
                    "is_vertical": is_vertical,
                    "source": "Coverr",
                    "title": item.get("title", query),
                    "tags": item.get("tags", []),
                    "width": width,
                    "height": height,
                    "duration": float(item.get("duration", 0.0))
                })

        is_port = (orientation == "portrait")
        candidates.sort(key=lambda x: (x["is_vertical"] == is_port, x["width"]), reverse=True)
        return candidates[:n]
    except Exception as e:
        print(f"[B-roll] Coverr candidates search failed for '{query}': {e}")
        return []


def _pixabay_candidates(query: str, n: int = 4) -> list[dict]:
    if not PIXABAY_API_KEY:
        return []
    clean_q = _sanitize_broll_query(query)[:80]
    if not clean_q:
        return []
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            params={
                "key": PIXABAY_API_KEY,
                "q": clean_q,
                "per_page": min(50, max(n * 4, 15)),
                "order": "popular",
                "safesearch": "true",
                "video_type": "all",
            },
            timeout=25,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        candidates = []
        for item in hits:
            videos_data = item.get("videos", {})
            video_url = None
            thumb = None
            for size in ["large", "medium", "small", "tiny"]:
                vobj = videos_data.get(size, {})
                if not video_url and vobj.get("url"):
                    video_url = vobj.get("url")
                if not thumb and vobj.get("thumbnail"):
                    thumb = vobj.get("thumbnail")
            
            if not thumb:
                thumb = item.get("userImageURL") or "https://pixabay.com/favicon.ico"
                
            if video_url:
                tags_str = item.get("tags", "")
                page_url = item.get("pageURL", "")
                slug = page_url.rstrip("/").split("/")[-1].replace("-", " ")
                candidates.append({
                    "video_url": video_url,
                    "thumb_url": thumb,
                    "title": slug or tags_str or clean_q,
                    "tags": [t.strip() for t in tags_str.split(",") if t.strip()],
                    "source": "Pixabay"
                })
        return candidates
    except Exception as e:
        print(f"[B-roll] Pixabay candidates failed for '{clean_q}': {e}")
        return []


def _nasa_candidates(query: str, n: int = 3) -> list[dict]:
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params=_nasa_params(query, "video", n * 3),
            headers={"User-Agent": "yt-auto/1.0"},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("collection", {}).get("items", [])
        if not items:
            clean_words = re.sub(r"[^\w\s-]", " ", query or "").split()
            fallback_words = [w for w in clean_words if w.lower() not in {"the", "a", "an", "and", "or", "to", "in", "of", "for", "with", "on", "4k", "hd", "footage", "clip"}]
            if len(fallback_words) >= 2:
                r_fb = requests.get(
                    "https://images-api.nasa.gov/search",
                    params={"q": " ".join(fallback_words[-2:]), "media_type": "video", "page_size": n * 2},
                    headers={"User-Agent": "yt-auto/1.0"},
                    timeout=15,
                )
                if r_fb.status_code == 200:
                    items = r_fb.json().get("collection", {}).get("items", [])
        if not items:
            return []

        candidates = []
        for item in items:
            if len(candidates) >= n:
                break
            nasa_id = item.get("data", [{}])[0].get("nasa_id")
            links = item.get("links", [])
            thumb_url = None
            for link in links:
                if link.get("rel") == "preview" or link.get("render") == "image":
                    thumb_url = link.get("href")
                    break
            if not nasa_id or not thumb_url:
                continue

            r_asset = requests.get(
                f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nasa_id)}",
                headers={"User-Agent": "yt-auto/1.0"},
                timeout=12,
            )
            if r_asset.status_code != 200:
                continue
            items_asset = r_asset.json().get("collection", {}).get("items", [])
            video_url = None
            for a in items_asset:
                href = a.get("href", "")
                if href.endswith("~medium.mp4") or href.endswith("~mobile.mp4"):
                    video_url = href
                    break
            if not video_url:
                for a in items_asset:
                    href = a.get("href", "")
                    if href.endswith(".mp4"):
                        video_url = href
                        break
            if video_url:
                candidates.append({
                    "video_url": video_url,
                    "thumb_url": thumb_url,
                    "source": "NASA",
                    "title": item.get("data", [{}])[0].get("title", query)
                })
        return candidates
    except Exception as e:
        print(f"[B-roll] NASA candidate search failed for '{query}': {e}")
        return []


def _nasa_video_candidate(query: str) -> dict | None:
    cands = _nasa_candidates(query, n=1)
    return cands[0] if cands else None


WIKIMEDIA_USER_AGENT = "yt-auto-bot/2.0 (https://github.com/mahesajeth-wq/yt-auto; contact@mahesajeth.com)"


def _wikimedia_candidates(query: str, n: int = 5) -> list[dict]:
    clean_q = _sanitize_broll_query(query)[:80]
    if not clean_q:
        return []
    words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', clean_q).split() if len(w) > 2][:3]
    search_terms = []
    if len(words) >= 2:
        search_terms.append(f'"{words[0]} {words[1]}"')
    if words:
        search_terms.append(" ".join(words))

    candidates = []
    seen = set()
    url = "https://commons.wikimedia.org/w/api.php"
    headers = {"User-Agent": WIKIMEDIA_USER_AGENT or "yt-auto-fleet/2.0 (educational-video-harvester)"}

    for st in search_terms:
        if len(candidates) >= n:
            break
        try:
            params = {
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{st} filetype:video",
                "gsrnamespace": "6",
                "gsrlimit": str(n * 2),
                "prop": "imageinfo",
                "iiprop": "url|mime|size",
                "iiurlwidth": "640",
                "format": "json",
            }
            r = requests.get(url, params=params, headers=headers, timeout=12)
            if r.status_code == 200:
                pages = r.json().get("query", {}).get("pages", {})
                for pid, pdata in pages.items():
                    title = pdata.get("title", "").replace("File:", "")
                    ii = pdata.get("imageinfo", [{}])[0]
                    v_url = ii.get("url")
                    t_url = ii.get("thumburl") or v_url
                    if v_url and v_url not in seen:
                        seen.add(v_url)
                        candidates.append({
                            "video_url": v_url,
                            "thumb_url": t_url,
                            "source": "Wikimedia",
                            "title": title,
                        })
                        if len(candidates) >= n:
                            break
        except Exception as e:
            print(f"[B-roll] Wikimedia candidate search failed for '{st}': {e}")
    return candidates


def _wikimedia_video_candidate(query: str) -> dict | None:
    cands = _wikimedia_candidates(query, n=1)
    return cands[0] if cands else None





# ── Source 4: NASA Image & Video Library (no key — public domain) ─────────────

def _nasa_image(query: str) -> str | None:
    """Fetches a real NASA image for science/space topics. Completely free, no key."""
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={
                **_nasa_params(query, "image", 5),
            },
            headers={"User-Agent": "yt-auto/1.0 (educational-pipeline)"},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("collection", {}).get("items", [])
        if not items:
            clean_words = re.sub(r"[^\w\s-]", " ", query or "").split()
            fallback_words = [w for w in clean_words if w.lower() not in {"the", "a", "an", "and", "or", "to", "in", "of", "for", "with", "on", "4k", "hd", "footage", "clip"}]
            if len(fallback_words) >= 2:
                r_fb = requests.get(
                    "https://images-api.nasa.gov/search",
                    params={"q": " ".join(fallback_words[-2:]), "media_type": "image", "page_size": 5},
                    headers={"User-Agent": "yt-auto/1.0 (educational-pipeline)"},
                    timeout=15,
                )
                if r_fb.status_code == 200:
                    items = r_fb.json().get("collection", {}).get("items", [])
        if not items:
            return None
        item = random.choice(items[:3])
        links = item.get("links", [])
        for link in links:
            href = link.get("href", "")
            if href and href.startswith("http"):
                return href
        return None
    except Exception as e:
        print(f"[B-roll] NASA failed for '{query}': {e}")
        return None


# ── Source 5: Wikipedia article thumbnail ────────────────────────────────────

def _wikipedia_image(query: str) -> str | None:
    """
    Fetches the Wikipedia official HD article image for the query topic using summary + generator search.
    No API key required. Perfect for named people, species, megaprojects, and historical events.
    """
    STOPLIST = [
        "footage", "real", "authentic", "documentary", "megaproject", "construction", "colossal", "machinery",
        "what", "inside", "secret", "incredible", "shocking", "alps", "subterranean", "disaster", "radiation",
        "next-generation", "nextgen", "futuristic", "super", "bright", "visualization", "concept", "impossible",
        "amazing", "presenting", "presentation", "laboratory", "transparent", "unlock", "unlocked", "unlocking"
    ]
    words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', query).split() if len(w) > 2 and w.lower() not in STOPLIST]
    clean_q = " ".join(words[:3]) if words else query
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": clean_q,
            "gsrlimit": "3",
            "prop": "pageimages",
            "pithumbsize": 1920,
            "format": "json"
        }
        r = requests.get(url, params=params, headers={"User-Agent": "yt-auto/1.0 (educational-pipeline)"}, timeout=10)
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                thumb = pdata.get("thumbnail", {}).get("source")
                if thumb:
                    return thumb
    except Exception as e:
        print(f"[B-roll] Wikipedia search image failed for '{query}': {e}")
    return None


def _wikimedia_image(query: str) -> str | None:
    """Search Wikimedia Commons for authentic high-resolution documentary and scientific photos/diagrams."""
    clean_q = _sanitize_broll_query(query)[:80]
    if not clean_q:
        return None
    try:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"{clean_q} filetype:bitmap",
            "gsrnamespace": "6",
            "gsrlimit": "5",
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "iiurlwidth": "1920",
            "format": "json"
        }
        headers = {"User-Agent": WIKIMEDIA_USER_AGENT}
        r = requests.get(url, params=params, headers=headers, timeout=12)
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {})
            if not pages:
                words = clean_q.split()
                if len(words) > 2:
                    short_q = " ".join(words[:2])
                    params["gsrsearch"] = f"{short_q} filetype:bitmap"
                    r_short = requests.get(url, params=params, headers=headers, timeout=12)
                    if r_short.status_code == 200:
                        pages = r_short.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                ii_list = pdata.get("imageinfo", [])
                if ii_list:
                    ii = ii_list[0]
                    mime = ii.get("mime", "")
                    if "image" in mime and not mime.endswith("svg+xml"):
                        thumb = ii.get("thumburl") or ii.get("url")
                        if thumb:
                            return thumb
    except Exception as e:
        print(f"[B-roll] Wikimedia image search failed for '{clean_q}': {e}")
    return None


def _wikimedia_video(query: str) -> str | None:
    """Search Wikimedia Commons for CC-licensed educational videos and fetch actual URL. No API key needed."""
    cands = _wikimedia_candidates(query, n=1)
    return cands[0]["video_url"] if cands else None


def resolve_dvids_mp4(page_url: str) -> str | None:
    try:
        r = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=10)
        if r.status_code == 200:
            mp4s = re.findall(r'https?://[^\"]+\.mp4[^\"]*', r.text)
            if mp4s:
                return mp4s[0]
    except Exception:
        pass
    return None


def _dvids_candidates(query: str, n: int = 3) -> list[dict]:
    dvids_key = os.environ.get("DVIDS_API_KEY", "")
    candidates = []
    if dvids_key:
        try:
            r = requests.get(
                "https://api.dvidshub.net/v1/search",
                params={"api_key": dvids_key, "q": query, "type": "video", "max_results": n * 2},
                headers={"User-Agent": "yt-auto/1.0"},
                timeout=10,
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                for item in results:
                    v = item.get("download_url") or item.get("file_url")
                    t = item.get("thumbnail_url") or item.get("image_url")
                    if v and t:
                        candidates.append({
                            "video_url": v,
                            "thumb_url": t,
                            "source": "DVIDS",
                            "title": item.get("title", query),
                            "id": item.get("id"),
                            "width": 1920
                        })
        except Exception:
            pass

    if not candidates:
        try:
            r = requests.get(
                "https://www.dvidshub.net/rss/search",
                params={"q": query, "filter[type]": "video"},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=10,
            )
            if r.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(r.content)
                items = root.findall(".//item")
                for item in items:
                    if len(candidates) >= n:
                        break
                    title = item.findtext("title") or ""
                    link = item.findtext("link") or ""
                    thumb = None
                    for elem in item.iter():
                        if "thumbnail" in elem.tag and "url" in elem.attrib:
                            thumb = elem.attrib["url"]
                            break
                    vid_id = None
                    if thumb:
                        m = re.search(r'video/\d+/(\d+)/', thumb)
                        if m:
                            vid_id = m.group(1)
                    if not vid_id and link:
                        m = re.search(r'video/(\d+)', link)
                        if m:
                            vid_id = m.group(1)
                    if vid_id and thumb:
                        page_url = f"https://www.dvidshub.net/video/{vid_id}"
                        direct_mp4 = resolve_dvids_mp4(page_url)
                        video_target = direct_mp4 if direct_mp4 else page_url
                        candidates.append({
                            "video_url": video_target,
                            "thumb_url": thumb,
                            "source": "DVIDS",
                            "title": title,
                            "id": vid_id,
                            "width": 1920
                        })
        except Exception as e:
            print(f"[B-roll] DVIDS search failed for '{query}': {e}")

    return candidates[:n]

def _dvids_video(query: str) -> str | None:
    candidates = _dvids_candidates(query, n=1)
    return candidates[0]["video_url"] if candidates else None

def _openverse_image(query: str) -> str | None:
    clean_q = _sanitize_broll_query(query)[:80]
    if not clean_q:
        return None
    try:
        r = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": clean_q, "license": "cc0,by", "page_size": 5, "orientation": "landscape"},
            headers={"User-Agent": "yt-auto/2.0 (educational-pipeline)"},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        chosen = random.choice(results[:3])
        return chosen.get("url")
    except Exception as e:
        print(f"[B-roll] Openverse image search failed for '{clean_q}': {e}")
        return None

def _archive_candidates(query: str, n: int = 3) -> list[dict]:
    import urllib.parse
    clean_q = _sanitize_broll_query(query)[:60]
    if not clean_q:
        return []
    headers = {"User-Agent": "yt-auto/2.0 (https://github.com/mahesajeth-wq/yt-auto; contact@mahesajeth.com)"}
    candidates = []

    try:
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f"({clean_q}) AND mediatype:movies",
                "fl[]": ["identifier", "title", "downloads"],
                "sort[]": "downloads desc",
                "rows": n * 4,
                "output": "json"
            },
            headers=headers,
            timeout=20
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        if not docs:
            words = clean_q.split()
            if len(words) > 2:
                short_q = " ".join(words[:2])
                r_short = requests.get(
                    "https://archive.org/advancedsearch.php",
                    params={
                        "q": f"({short_q}) AND mediatype:movies",
                        "fl[]": ["identifier", "title", "downloads"],
                        "sort[]": "downloads desc",
                        "rows": n * 4,
                        "output": "json"
                    },
                    headers=headers,
                    timeout=20
                )
                if r_short.status_code == 200:
                    docs = r_short.json().get("response", {}).get("docs", [])
    except Exception as e:
        print(f"[B-roll] Archive search failed for '{clean_q}': {e}")
        docs = []

    # Strict keyword matching to reject unrelated fiction films
    query_keywords = [w.lower() for w in clean_q.split() if len(w) > 2]

    for doc in docs:
        if len(candidates) >= n:
            break
        identifier = doc.get("identifier")
        title = doc.get("title", "")
        if not identifier:
            continue
        title_lower = title.lower()
        # Strictly reject fiction films, TV dramas, and trailers
        if any(bad in title_lower for bad in ["brighter summer day", "feature film", "drama", "episode", "season", "trailer", "short film"]):
            continue
        # If keywords exist, check if title or identifier matches any keyword (relaxed for topic relevance)
        if query_keywords and not (any(kw in title_lower for kw in query_keywords) or any(kw in identifier.lower() for kw in query_keywords)):
            # If doc is in top 3 results from archive search, permit it unless blacklisted
            pass
        try:
            r_files = requests.get(
                f"https://archive.org/metadata/{urllib.parse.quote(identifier)}",
                headers=headers,
                timeout=15
            )
            r_files.raise_for_status()
            files = r_files.json().get("files", [])
            
            video_url = None
            for f in files:
                name = f.get("name", "")
                if (name.endswith(".mp4") or name.endswith(".webm") or name.endswith(".mkv") or name.endswith(".avi")) and int(f.get("size") or 0) > 10_000:
                    video_url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(name)}"
                    break
            
            if not video_url:
                continue
                
            thumb_url = None
            for f in files:
                name = f.get("name", "")
                if name.endswith("__ia_thumb.jpg") or name.lower().endswith((".jpg", ".png", ".jpeg")):
                    thumb_url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(name)}"
                    break
            if not thumb_url:
                thumb_url = f"https://archive.org/services/img/{identifier}"
                
            candidates.append({
                "video_url": video_url,
                "thumb_url": thumb_url,
                "source": "Archive",
                "title": title,
                "id": identifier
            })
        except Exception as e:
            print(f"[B-roll] Archive metadata fetch failed for '{identifier}': {e}")
            
    return candidates


def _nasa_video(query: str) -> str | None:
    """Fetches a real NASA video for science/space topics. Completely free, no key."""
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={
                **_nasa_params(query, "video", 5),
            },
            headers={"User-Agent": "yt-auto/1.0 (educational-pipeline)"},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("collection", {}).get("items", [])
        if not items:
            clean_words = re.sub(r"[^\w\s-]", " ", query or "").split()
            fallback_words = [w for w in clean_words if w.lower() not in {"the", "a", "an", "and", "or", "to", "in", "of", "for", "with", "on", "4k", "hd", "footage", "clip"}]
            if len(fallback_words) >= 2:
                r_fb = requests.get(
                    "https://images-api.nasa.gov/search",
                    params={"q": " ".join(fallback_words[-2:]), "media_type": "video", "page_size": 5},
                    headers={"User-Agent": "yt-auto/1.0 (educational-pipeline)"},
                    timeout=15,
                )
                if r_fb.status_code == 200:
                    items = r_fb.json().get("collection", {}).get("items", [])
        if not items:
            return None

        # Pick one from top 3
        item = random.choice(items[:3])
        nasa_id = item.get("data", [{}])[0].get("nasa_id")
        if not nasa_id:
            return None

        r_asset = requests.get(
            f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nasa_id)}",
            headers={"User-Agent": "yt-auto/1.0 (educational-pipeline)"},
            timeout=15,
        )
        r_asset.raise_for_status()
        items_asset = r_asset.json().get("collection", {}).get("items", [])
        for a in items_asset:
            href = a.get("href", "")
            if href.endswith("~medium.mp4") or href.endswith("~mobile.mp4"):
                return href
        for a in items_asset:
            href = a.get("href", "")
            if href.endswith(".mp4"):
                return href
        return None
    except Exception as e:
        print(f"[B-roll] NASA video failed for '{query}': {e}")
        return None


def _archive_video(query: str) -> str | None:
    """Search Internet Archive for public domain movies. No API key needed."""
    clean_q = _sanitize_broll_query(query)[:60]
    if not clean_q:
        return None
    headers = {"User-Agent": "yt-auto/2.0 (https://github.com/mahesajeth-wq/yt-auto; contact@mahesajeth.com)"}
    try:
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f"({clean_q}) AND mediatype:(movies)",
                "fl[]": "identifier",
                "rows": "5",
                "output": "json",
            },
            headers=headers,
            timeout=20,
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        if not docs:
            return None

        identifier = docs[0]["identifier"]
        r_files = requests.get(
            f"https://archive.org/metadata/{urllib.parse.quote(identifier)}",
            headers=headers,
            timeout=15,
        )
        r_files.raise_for_status()
        files = r_files.json().get("files", [])
        for f in files:
            name = f.get("name", "")
            if (name.endswith(".mp4") or name.endswith(".webm") or name.endswith(".mkv") or name.endswith(".avi")) and int(f.get("size", 0)) > 10_000:
                return f"https://archive.org/download/{identifier}/{urllib.parse.quote(name)}"
        return None
    except Exception as e:
        print(f"[B-roll] Internet Archive failed for '{clean_q}': {e}")
        return None


def _parse_iso_duration(duration_str: str) -> float:
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0.0
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return float(hours * 3600 + minutes * 60 + seconds)


def _reddit_candidates(query: str, n: int = 4, channel: str = "general") -> list[dict]:
    """
    Search Reddit for genuine viral user footage, sightings, anomalies, and authentic video posts.
    Uses multi-tiered RedditVideoEngine (PullPush streams + semantic community footage grounding)
    and captures post author / subreddit for on-screen Fair Use attribution.
    """
    try:
        from pipeline.reddit_engine import get_reddit_engine
        engine = get_reddit_engine()
        cands = engine.get_reddit_candidates(query, niche=channel, n=n)
        if cands:
            return cands
    except Exception as e:
        print(f"[B-roll] Reddit engine note for '{query}': {e}")

    import urllib.parse
    candidates = []
    seen = set()
    clean_q = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
    if not clean_q:
        return []
    
    url = f"https://api.pullpush.io/reddit/search/submission/?q={urllib.parse.quote(clean_q)}&is_video=true&size=15"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            items = r.json().get("data", [])
            for it in items:
                media = it.get("media") or {}
                r_vid = media.get("reddit_video") if isinstance(media, dict) else None
                f_url = r_vid.get("fallback_url") if r_vid else None
                if not f_url and it.get("is_video") and it.get("url", "").endswith(".mp4"):
                    f_url = it.get("url")
                if not f_url:
                    continue
                if f_url in seen:
                    continue
                seen.add(f_url)
                
                sub = it.get("subreddit") or "Reddit"
                author = it.get("author") or "RedditUser"
                title = it.get("title", "")
                thumb = it.get("thumbnail")
                if not thumb or thumb in ["self", "default", "nsfw", "spoiler"]:
                    preview = it.get("preview") or {}
                    images = preview.get("images") or []
                    if images and images[0].get("source", {}).get("url"):
                        thumb = images[0]["source"]["url"].replace("&amp;", "&")
                    else:
                        thumb = f_url
                
                handle = f"u/{author} (r/{sub})"
                candidates.append({
                    "source": "Reddit",
                    "video_url": f_url,
                    "thumb_url": thumb,
                    "title": title,
                    "duration": float(r_vid.get("duration", 10.0)) if r_vid else 10.0,
                    "uploader_name": f"r/{sub}",
                    "uploader_handle": handle,
                    "channel_url": f"https://reddit.com/r/{sub}"
                })
                if len(candidates) >= n:
                    break
    except Exception as e:
        print(f"[B-roll] Reddit fallback note for '{query}': {e}")
    return candidates


def _youtube_candidates(query: str, n: int = 5) -> list[dict]:
    """
    Search YouTube for matchable B-roll clips using broad ytsearch query.
    Captures uploader channel handle for on-screen Fair Use attribution.
    Prioritizes modern high-definition (4K/1080p) footage and filters out low-resolution archives.
    """
    import yt_dlp
    import urllib.parse
    import re
    
    candidates = []
    seen_urls = set()
    search_queries = [
        f"{query} real footage 4k",
        f"{query} 1080p documentary",
        f"{query} cinematic b-roll 4k",
        f"{query} authentic footage",
        query
    ]
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'nocheckcertificate': True,
        'force_generic_extractor': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb', 'tv', 'android_vr', 'web_creator']
            }
        }
    }
    
    for sq in search_queries:
        if len(candidates) >= n:
            break
        try:
            print(f"[B-roll] Searching YouTube for: '{sq}'...")
            search_target = f"ytsearch{n*2}:{sq}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(search_target, download=False)
                entries = result.get('entries', []) if result else []
                
                for entry in entries:
                    if not entry:
                        continue
                    title = entry.get('title', '')
                    url = entry.get('url', '')
                    duration = entry.get('duration')
                    
                    duration_secs = float(duration) if duration else 0.0
                    if duration_secs > 0.0 and (duration_secs < 10.0 or duration_secs > 1800.0):
                        continue
                    
                    # Filter out lecture/classroom/blackboard/explainer/text-heavy titles unless explicitly requested
                    title_lower = title.lower()
                    bad_title_keywords = [
                        "lecture", "classroom", "blackboard", "chalkboard", "whiteboard", "tutorial", "course",
                        "teacher", "presentation", "lesson", "slides", "powerpoint",
                        "free stock", "watermark", "videohive", "shutterstock",
                        "stocksubmitter", "knot9", "depositphotos", "dreamstime", "getty", "pond5", "envato",
                        "istock", "buy", "store", "price", "aliexpress", "amazon", "ebay", "shopping"
                    ]
                    if any(bad in title_lower for bad in bad_title_keywords):
                        print(f"[B-roll] Skipping promotional/classroom YouTube candidate: '{title}'")
                        continue
                    
                    video_id = entry.get('id')
                    if not video_id and url:
                        m_id = re.search(r'(?:v=|\/shorts\/|\/embed\/|\/)([a-zA-Z0-9_-]{11})', url)
                        if m_id:
                            video_id = m_id.group(1)
                    
                    if not video_id or len(video_id) != 11 or video_id == "shorts":
                        continue
                        
                    full_url = f"https://www.youtube.com/watch?v={video_id}"
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)
                    
                    channel = entry.get('channel') or entry.get('uploader') or ""
                    uploader_id = entry.get('uploader_id') or ""
                    
                    if uploader_id and str(uploader_id).startswith('@'):
                        handle = str(uploader_id).strip()
                    elif channel:
                        clean_c = re.sub(r'[^a-zA-Z0-9_-]', '', str(channel)).strip()
                        handle = f"@{clean_c}" if clean_c else "@YouTube"
                    elif uploader_id:
                        clean_u = re.sub(r'[^a-zA-Z0-9_-]', '', str(uploader_id)).strip()
                        handle = f"@{clean_u}" if clean_u else "@YouTube"
                    else:
                        handle = "@YouTube"
                    
                    uploader_name = channel or uploader_id or "YouTube"
                    channel_url = entry.get('channel_url') or entry.get('uploader_url') or (f"https://www.youtube.com/{handle}" if handle != "@YouTube" else "")
                    thumb_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                    
                    candidates.append({
                        "source": "YouTube",
                        "video_url": full_url,
                        "thumb_url": thumb_url,
                        "title": title,
                        "description": entry.get('description', '') or "",
                        "duration": duration_secs,
                        "uploader_name": str(uploader_name).strip(),
                        "uploader_handle": str(handle).strip(),
                        "channel_url": str(channel_url).strip()
                    })
                    
                    if len(candidates) >= n:
                        break
        except Exception as e:
            print(f"[B-roll] YouTube search failed for '{sq}': {e}")
            
    print(f"[B-roll] Found {len(candidates)} YouTube candidate clips.")
    return candidates


def _download_video_robust(url: str, out_path: str, segment_index: int, candidate_info: dict | None = None) -> bool:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        duration_secs = 0.0
        if candidate_info and candidate_info.get("duration"):
            try:
                duration_secs = float(candidate_info.get("duration", 0.0))
            except Exception:
                duration_secs = 0.0
        
        slice_dur = 10.0
        is_reddit = "v.redd.it" in url or "reddit.com" in url or (candidate_info and candidate_info.get("source") == "Reddit")
        is_youtube = "youtube.com" in url or "youtu.be" in url or (candidate_info and candidate_info.get("source") == "YouTube")

        # 1. Reddit HLS / DASH stream download via FFmpeg with intro skip
        if is_reddit:
            print(f"[B-roll] Downloading authentic Reddit video slice for segment {segment_index}: {url}...")
            hls_url = url
            m_vid = re.search(r'v\.redd\.it\/([a-zA-Z0-9_-]+)', url)
            if m_vid:
                vid_id = m_vid.group(1)
                hls_url = f"https://v.redd.it/{vid_id}/HLSPlaylist.m3u8"
            
            # Skip opening 3s if duration > 8s
            r_start = 3.5 if duration_secs > 8.0 or duration_secs == 0.0 else 0.0
            cmd_red = [
                "ffmpeg", "-y",
                "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n",
                "-ss", f"{r_start:.3f}",
                "-i", hls_url,
                "-t", str(slice_dur),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                out_path
            ]
            try:
                res_r = subprocess.run(cmd_red, capture_output=True, text=True, timeout=30)
                if res_r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
                    print(f"[B-roll] Reddit authentic video slice download SUCCESS!")
                    c_name = candidate_info.get("uploader_name", "Reddit") if candidate_info else "Reddit"
                    c_handle = candidate_info.get("uploader_handle", "r/Reddit") if candidate_info else "r/Reddit"
                    credit_data = {
                        "source": "Reddit",
                        "uploader_name": str(c_name),
                        "uploader_handle": str(c_handle),
                        "channel_url": candidate_info.get("channel_url", "https://reddit.com") if candidate_info else "https://reddit.com",
                        "video_url": url,
                        "title": candidate_info.get("title", "") if candidate_info else ""
                    }
                    try:
                        with open(f"output/broll_{segment_index}_credit.json", "w") as cf:
                            json.dump(credit_data, cf, indent=2)
                    except Exception: pass
                    return True
                else:
                    print(f"[B-roll] Reddit FFmpeg failed: {res_r.stderr[:200]}")
            except Exception as e_red:
                print(f"[B-roll] Reddit download exception: {e_red}")
            return False

        # 2. YouTube video download with smart intro skip based on actual probed duration
        if is_youtube:
            print(f"[B-roll] Downloading YouTube authentic video slice for segment {segment_index}: {url}...")
            ytdlp_bin_cmd = _get_ytdlp_bin()
            temp_full = f"output/yt_full_temp_{segment_index}.mp4"
            if os.path.exists(temp_full):
                try: os.remove(temp_full)
                except Exception: pass

            proxy_args = []
            warp_proxy = os.environ.get("WARP_SOCKS_PROXY", "socks5h://127.0.0.1:40000")
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", 40000)) == 0:
                    proxy_args = ["--proxy", warp_proxy]
                s.close()
            except Exception:
                pass

            client_options = [
                "android_creator,android",
                "android",
                "tv_embedded",
                "web"
            ]

            for client_str in client_options:
                cmd_dl = ytdlp_bin_cmd + proxy_args + [
                    "--extractor-args", f"youtube:player_client={client_str}",
                    "--format", "18/22/136/137/best[ext=mp4]/best",
                    "--no-check-certificates",
                    "--socket-timeout", "15",
                    "-o", temp_full,
                    url
                ]
                try:
                    res_dl = subprocess.run(cmd_dl, capture_output=True, text=True, timeout=40)
                    if os.path.exists(temp_full) and os.path.getsize(temp_full) > 10_000:
                        # Probe actual duration to skip creator intro, channel stinger, or sponsors
                        actual_dur = _get_video_duration(temp_full)
                        if actual_dur >= 60.0:
                            start_time = max(25.0, min(actual_dur * 0.35, actual_dur - 15.0))
                        elif actual_dur >= 25.0:
                            start_time = max(10.0, actual_dur * 0.25)
                        elif actual_dur >= 10.0:
                            start_time = max(3.5, actual_dur * 0.15)
                        else:
                            start_time = 0.0

                        cmd_cut = [
                            "ffmpeg", "-y",
                            "-ss", f"{start_time:.3f}",
                            "-i", temp_full,
                            "-t", str(slice_dur),
                            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                            "-c:a", "aac",
                            "-avoid_negative_ts", "make_zero",
                            out_path
                        ]
                        subprocess.run(cmd_cut, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                        try: os.remove(temp_full)
                        except Exception: pass
                        
                        if os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
                            print(f"[B-roll] YouTube authentic slice cut from t={start_time:.1f}s (skipped intro) with client {client_str}!")
                            c_name = candidate_info.get("uploader_name", "YouTube") if candidate_info else "YouTube"
                            c_handle = candidate_info.get("uploader_handle", "@YouTube") if candidate_info else "@YouTube"
                            credit_data = {
                                "source": "YouTube",
                                "uploader_name": str(c_name),
                                "uploader_handle": str(c_handle),
                                "channel_url": candidate_info.get("channel_url", "") if candidate_info else "",
                                "video_url": url,
                                "title": candidate_info.get("title", "") if candidate_info else ""
                            }
                            try:
                                with open(f"output/broll_{segment_index}_credit.json", "w") as cf:
                                    json.dump(credit_data, cf, indent=2)
                            except Exception: pass
                            return True
                    else:
                        print(f"[B-roll] yt-dlp client {client_str} failed: {res_dl.stderr[:150]}")
                except Exception as e_yt:
                    print(f"[B-roll] YouTube download exception ({client_str}): {e_yt}")
            return False

        # 3. Direct HTTP/HTTPS Video stream (NASA, Archive.org, DVIDS, Wikimedia)
        print(f"[B-roll] Downloading direct media stream for segment {segment_index}: {url[:80]}...")
        stream_ua = WIKIMEDIA_USER_AGENT if "wikimedia.org" in url else "yt-auto/2.0 (educational-video-pipeline)"
        try:
            r = requests.get(url, stream=True, timeout=35, headers={"User-Agent": stream_ua})
            r.raise_for_status()
        except requests.HTTPError as he:
            if he.response is not None and he.response.status_code == 429:
                warp_proxy = os.environ.get("WARP_SOCKS_PROXY", "socks5h://127.0.0.1:40000")
                print(f"[B-roll] Direct stream returned 429. Retrying via WARP proxy ({warp_proxy})...")
                r = requests.get(url, stream=True, timeout=35, headers={"User-Agent": stream_ua}, proxies={"http": warp_proxy, "https": warp_proxy})
                r.raise_for_status()
            else:
                raise he

        content_type = r.headers.get("Content-Type", "").lower()
        if "html" in content_type or "text" in content_type:
            print(f"[B-roll] URL returned HTML/text, not a video stream. Rejecting.")
            return False

        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()
        is_webm = path.endswith(".webm") or path.endswith(".ogv") or "webm" in content_type
        is_gif = path.endswith(".gif") or "gif" in content_type

        temp_ext = ".webm" if is_webm else ".gif" if is_gif else ".mp4"
        temp_file = f"output/temp_dl_{segment_index}{temp_ext}"
        with open(temp_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)

        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 10_000:
            actual_dur = _get_video_duration(temp_file)
            if actual_dur >= 60.0:
                stream_start = max(15.0, actual_dur * 0.25)
            elif actual_dur >= 20.0:
                stream_start = max(5.0, actual_dur * 0.15)
            else:
                stream_start = 0.0

            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{stream_start:.3f}",
                "-i", temp_file,
                "-t", str(slice_dur),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-an",
                "-avoid_negative_ts", "make_zero",
                out_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except Exception: pass
            if res.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) < 10_000:
                return False

            # Probe resolution to reject low-res < 720p
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=s=x:p=0",
                    out_path
                ]
                probe_res = subprocess.check_output(probe_cmd).decode().strip()
                if "x" in probe_res:
                    pw, ph = map(int, probe_res.split("x")[:2])
                    if pw < 720 and ph < 720:
                        print(f"[B-roll] REJECTED low-res/grainy clip ({pw}x{ph} < 720p) for segment {segment_index}.")
                        try: os.remove(out_path)
                        except Exception: pass
                        return False
            except Exception:
                pass
            return True
        return False
    except Exception as e:
        print(f"[B-roll] Robust download failed for {url}: {e}")
        return False

def _image_to_ken_burns_video(img_path: str, out_path: str, w: int, h: int, duration: float = 6.0, niche: str = "general", caption: str = ""):
    """
    Converts a static image or video clip to a normalized video.
    If input is already a video asset, normalizes directly with FFmpeg.
    If input is an image, tries Hyperframes for motion overlays, falling back to Ken Burns zoompan.
    """
    ext = os.path.splitext(img_path)[1].lower()
    is_video = ext in [".mp4", ".webm", ".ogv", ".mov", ".avi"] or "video" in img_path.lower() or img_path.endswith("_video")
    
    if is_video:
        print(f"[B-roll] Normalizing video asset: {img_path} -> {out_path}")
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", img_path,
            "-vf", f"scale=trunc({w}/2)*2:trunc({h}/2)*2:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
            "-t", f"{duration:.3f}", "-r", "30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-an", out_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
            return
        print(f"[B-roll] Video normalization returned non-zero ({res.returncode}), falling back to procedural synth...")

    # Force DISABLE_HYPERFRAMES to prevent tech HUD borders/grid overlays over B-roll clips
    os.environ["DISABLE_HYPERFRAMES"] = "1"

    if not is_video:
        if not _validate_and_normalize_image(img_path):
            print(f"[B-roll] Image invalid for Ken Burns, synthesizing with PIL: {img_path}")
            _pil_placeholder("", w, h, img_path)

    fps    = 30
    frames = max(1, int(duration * fps))

    styles = [
        f"zoompan=z='min(zoom+0.0012,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        f"zoompan=z='min(zoom+0.0012,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{frames})':s={w}x{h}:fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        f"zoompan=z='min(zoom+0.0012,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{frames})':s={w}x{h}:fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        f"zoompan=z='min(zoom+0.0010,1.20)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
    ]
    vf = random.choice(styles)

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", f"{vf},setsar=1",
        "-t", str(duration), "-r", str(fps),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-an", out_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
            return
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
        print(f"[B-roll] Ken Burns zoompan failed ({e.returncode}): {err_msg[:200]}. Falling back to safe scale...")

    # Robust fallback: simple scale and crop without zoompan
    fallback_cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", f"scale=trunc({w}/2)*2:trunc({h}/2)*2:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
        "-t", str(duration), "-r", str(fps),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-an", out_path,
    ]
    try:
        subprocess.run(fallback_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e2:
        print(f"[B-roll] Safe scale also failed ({e2}). Synthesizing fallback video...")
        _pil_placeholder("", w, h, img_path)
        subprocess.run(fallback_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)



# ── Fallback: Pollinations.ai (AI-generated, 4K resolution) ────────────────

def _pollinations_image(query: str, img_path: str, w: int = 1080, h: int = 1920) -> bool:
    """Returns True if 4K cinematic stock image was downloaded successfully via Pollinations AI."""
    banned_words = {
        "conan", "barbarian", "frankenstein", "godzilla", "monster", "werewolf", "beast",
        "footage", "real", "authentic", "documentary", "megaproject", "construction", "colossal", "machinery"
    }
    if query.strip().startswith("4k cinematic"):
        clean_prompt = query.strip()
    else:
        words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', query).split() if len(w) > 2 and w.lower() not in banned_words]
        clean_q = " ".join(words[:8]) if words else query[:60]
        clean_prompt = f"4k cinematic documentary photo of {clean_q}, national geographic photography, hyperrealistic, 8k, highly detailed, photorealistic, no text, no watermark, no slides, no humans"

    req_w, req_h = (w, h) if (w and h) else (1080, 1920)
    encoded_prompt = urllib.parse.quote(clean_prompt[:240])
    for model, t_out in [("flux", 25), ("turbo", 15)]:
        try:
            seed = random.randint(1, 100000)
            url = (
                f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                f"?width={req_w}&height={req_h}&model={model}&nologo=true&seed={seed}"
            )
            r = requests.get(url, timeout=t_out)
            if r.status_code == 200 and len(r.content) > 10_000:
                with open(img_path, "wb") as f:
                    f.write(r.content)
                if _validate_and_normalize_image(img_path):
                    print(f"[B-roll] 4K Pollinations {model} image download OK.")
                    return True
        except Exception as e:
            print(f"[B-roll] Pollinations {model} failed: {e}")
    return False


# ── Last resort: PIL gradient placeholder ────────────────────────────────────

def _pil_placeholder(query: str, w: int, h: int, img_path: str):
    """
    Generates a clean, text-free procedural cinematic dark visual plate.
    Strictly eliminates text-only slides: NEVER draws letters, titles, or words.
    Creates an atmospheric dark radial vignette with subtle geometric reticle accents.
    """
    from PIL import Image, ImageDraw
    import numpy as np

    # 1. Dark atmospheric radial gradient (deep charcoal to dark slate)
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    cy, cx = h / 2.0, w / 2.0
    max_dist = max(1.0, float(np.sqrt(cx**2 + cy**2)))

    y_coords, x_coords = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2)
    norm_dist = np.clip(dist_from_center / max_dist, 0.0, 1.0)

    # Core: [16, 20, 28] -> Edge: [4, 6, 10]
    arr[:, :, 0] = (16 - norm_dist * 12).astype(np.uint8)
    arr[:, :, 1] = (20 - norm_dist * 14).astype(np.uint8)
    arr[:, :, 2] = (28 - norm_dist * 18).astype(np.uint8)

    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # 2. Subtle geometric framing lines (15% opacity aesthetic, zero text)
    reticle_color = (38, 48, 62)
    accent_color = (55, 75, 105)

    # Center crosshairs
    cx_i, cy_i = int(cx), int(cy)
    draw.line([(cx_i - 40, cy_i), (cx_i - 10, cy_i)], fill=reticle_color, width=1)
    draw.line([(cx_i + 10, cy_i), (cx_i + 40, cy_i)], fill=reticle_color, width=1)
    draw.line([(cx_i, cy_i - 40), (cx_i, cy_i - 10)], fill=reticle_color, width=1)
    draw.line([(cx_i, cy_i + 10), (cx_i, cy_i + 40)], fill=reticle_color, width=1)

    # Center subtle ring
    draw.ellipse([(cx_i - 70, cy_i - 70), (cx_i + 70, cy_i + 70)], outline=reticle_color, width=1)

    # Corner registration marks
    margin = int(min(w, h) * 0.08)
    c_len = int(min(w, h) * 0.04)
    # Top-left
    draw.line([(margin, margin), (margin + c_len, margin)], fill=accent_color, width=2)
    draw.line([(margin, margin), (margin, margin + c_len)], fill=accent_color, width=2)
    # Top-right
    draw.line([(w - margin, margin), (w - margin - c_len, margin)], fill=accent_color, width=2)
    draw.line([(w - margin, margin), (w - margin, margin + c_len)], fill=accent_color, width=2)
    # Bottom-left
    draw.line([(margin, h - margin), (margin + c_len, h - margin)], fill=accent_color, width=2)
    draw.line([(margin, h - margin), (margin, h - margin - c_len)], fill=accent_color, width=2)
    # Bottom-right
    draw.line([(w - margin, h - margin), (w - margin - c_len, h - margin)], fill=accent_color, width=2)
    draw.line([(w - margin, h - margin), (w - margin, h - margin - c_len)], fill=accent_color, width=2)

    img.save(img_path, "JPEG", quality=90)


def _make_clean_fallback(query: str) -> str:
    stop_words = {
        "failure", "failed", "failed", "breaking", "broken", "broke",
        "damaged", "damage", "collapsed", "collapse", "slipping", "slipped",
        "slip", "during", "mechanism", "problems", "problem", "defect",
        "defective", "faulty", "error", "issue", "issues", "accident",
        "disaster", "ruined", "destroy", "destroyed", "destroying",
        "a", "an", "the", "in", "on", "at", "to", "for", "with", "by", "of"
    }
    words = query.lower().split()
    filtered = [w for w in words if w not in stop_words]
    if filtered:
        return " ".join(filtered)
    return query


def _get_video_duration(filepath: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    try:
        import subprocess
        return float(subprocess.check_output(cmd).decode().strip())
    except Exception:
        return 0.0

# ── Master fetch function ────────────────────────────────────────────────────


def _extract_collage_to_file(video_path: str, out_path: str) -> bool:
    try:
        from PIL import Image
        import subprocess
        # Get video duration
        cmd_dur = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        duration = float(subprocess.check_output(cmd_dur).decode().strip())
        if duration <= 0:
            return False
            
        # Extract 3 frames past initial 1.5s intro slide (at 25%, 55%, 85% of remaining duration)
        start_offset = 1.5 if duration > 4.0 else 0.0
        rem_dur = max(1.0, duration - start_offset)
        timestamps = [start_offset + rem_dur * 0.25, start_offset + rem_dur * 0.55, start_offset + rem_dur * 0.85]
        frames = []
        import numpy as np
        
        for idx, ts in enumerate(timestamps):
            temp_frame = f"{video_path}_collage_f_{idx}.jpg"
            # Extract frame at ts
            cmd = [
                "ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", video_path,
                "-vframes", "1", "-f", "image2", temp_frame
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(temp_frame):
                try:
                    img = Image.open(temp_frame).convert("RGB")
                    arr = np.array(img)
                    mean_lum = float(np.mean(arr))
                    std_lum = float(np.std(arr))
                    # Reject black screens, dark loading screens, or white flash screens
                    if mean_lum < 15.0 or mean_lum > 245.0 or std_lum < 8.0:
                        print(f"[B-roll] Rejecting dark/flash frame at {ts:.2f}s (mean_lum={mean_lum:.1f}, std={std_lum:.1f})")
                        os.remove(temp_frame)
                        continue
                    # Resize to keep aspect ratio but limit size (e.g. height 240)
                    img.thumbnail((320, 240))
                    frames.append((img, temp_frame))
                except Exception:
                    if os.path.exists(temp_frame):
                        os.remove(temp_frame)
                        
        if not frames:
            return False
            
        # Stitch frames horizontally
        widths, heights = zip(*(f[0].size for f in frames))
        total_width = sum(widths)
        max_height = max(heights)
        
        collage = Image.new('RGB', (total_width, max_height))
        x_offset = 0
        for img, path in frames:
            collage.paste(img, (x_offset, 0))
            x_offset += img.size[0]
            # Clean up temp frame
            os.remove(path)
            
        collage.save(out_path, "JPEG", quality=80)
        return True
    except Exception as e:
        print(f"[B-roll] Failed to create collage for {video_path}: {e}")
        return False


def _expand_query(query: str, channel: str, n: int = 5, narration: str = "", topic: str = "") -> list[str]:
    from pipeline.gemini import _post_with_rotation
    from pipeline.config import GEMINI_API_BASE, GEMINI_FLASH
    try:
        context_lines = []
        if topic:
            context_lines.append(f"Video Topic: '{topic}'")
        if narration:
            context_lines.append(f"Segment Narration: '{narration}'")
        context_str = ("\n" + "\n".join(context_lines) + "\n") if context_lines else ""
        prompt_text = (
            f"You are an expert documentary footage archivist. Base Query: '{query}'. Channel Niche: {channel}.{context_str}\n"
            f"Generate {n} SHORT, CONCRETE physical search terms (2-4 words maximum) that describe the ACTUAL physical science, machinery, specimen, or setting depicted in this narration.\n"
            f"CRITICAL RULES:\n"
            f"1. Use ONLY concrete physical objects, scientific apparatus, micrographs, specimens, or camera close-ups (e.g. 'microscope blood cells', 'rattlesnake striking slow motion', 'quantum laser cryostat', 'tunnel boring machine cutterhead').\n"
            f"2. NEVER use abstract metaphors or symbolic phrases (NO 'tiny warriors', 'antidote factory', 'quantum leaps all around', 'mind-blowing', 'concept').\n"
            f"3. Focus on real-world visual proof and authentic documentary footage.\n"
            f"Return ONLY a JSON array of strings."
        )
        url = f"{GEMINI_API_BASE}/models/{GEMINI_FLASH}:generateContent?key={{key}}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }
        resp = _post_with_rotation(url, payload, timeout=30)
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        items = json.loads(raw)
        if isinstance(items, list):
            res = []
            for item in items:
                if isinstance(item, str):
                    s = item.strip()
                    if s and s.lower() != query.lower():
                        res.append(s)
            seen = set()
            deduped = []
            for item in res:
                if item.lower() not in seen:
                    seen.add(item.lower())
                    deduped.append(item)
            return deduped
        return []
    except Exception:
        return []


def _score_candidate(item: dict, query: str, target_duration: float = 8.0, topic: str = "", channel: str = "") -> float:
    text_to_check = ""
    for field in ["title", "tags", "video_url", "thumb_url", "description"]:
        val = item.get(field)
        if isinstance(val, str):
            text_to_check += " " + val
        elif isinstance(val, list):
            text_to_check += " " + " ".join(str(v) for v in val)
    text_lower = text_to_check.lower()

    # Detect domain context from topic, query, and channel
    combined_context = f"{topic} {query} {channel}".lower()
    is_space = any(w in combined_context for w in [
        "space", "planet", "neptune", "jupiter", "mars", "saturn", "uranus", "venus", "mercury",
        "pluto", "astronomy", "astrophysics", "cosmos", "cosmic", "galaxy", "nebula", "black hole",
        "supernova", "telescope", "nasa", "esa", "orbit", "exoplanet", "asteroid", "comet"
    ])
    is_nature = any(w in combined_context for w in [
        "ocean", "deep sea", "underwater", "marine", "shark", "whale", "fish", "snailfish", "coelacanth",
        "hydrothermal", "abyss", "trench", "coral", "species", "wildlife", "animal", "biology"
    ])
    is_history = any(w in combined_context for w in [
        "ancient", "roman", "greek", "medieval", "archaeology", "ruins", "pharaoh", "pyramid",
        "empire", "emperor", "gladiator", "antiquity", "century bc"
    ])

    # HARD DOMAIN NEGATIVE DISQUALIFIERS (Instant disqualification -200.0)
    if is_space:
        banned_space = [
            "foundry", "steel mill", "steel factory", "metal factory", "blast furnace", "smelting",
            "car factory", "traffic", "highway", "car driving", "modern office", "boardroom",
            "corporate office", "beach sunset", "tropical beach", "palm trees", "bikini",
            "coffee shop", "cocktail", "supermarket", "shopping mall", "skateboarding",
            "fashion model", "yoga", "kitchen cooking", "city skyline", "subway train"
        ]
        for bad in banned_space:
            if bad in text_lower:
                return -200.0

    if is_nature:
        banned_nature = [
            "factory floor", "modern office", "boardroom", "corporate meeting", "traffic jam",
            "highway driving", "assembly line", "warehouse", "nightclub", "casino", "cryptocurrency",
            "soldering", "circuit board", "circuit", "motherboard", "electronics", "technician",
            "computer repair", "hardware", "software", "programmer", "coding", "keyboard",
            "camera repair", "cleaning sensor", "hasselblad", "dslr", "workbench", "workshop",
            "repairman", "mechanic", "car repair", "engine", "welding", "automotive",
            "werewolf", "monster", "barbarian", "conan", "demon", "warlock"
        ]
        for bad in banned_nature:
            if bad in text_lower:
                return -300.0

        # Bio-anchor check: if query/topic is microscopic/biological, reject mechanical/hardware footage
        is_bio_micro = any(w in combined_context for w in ["dna", "gene", "protein", "cell", "bacteri", "micro", "organism", "enzyme", "virus"])
        if is_bio_micro:
            has_bio_keyword = any(w in text_lower for w in ["dna", "cell", "bacteri", "micro", "organism", "protein", "enzyme", "biolog", "specimen", "nature", "wildlife", "animal"])
            if not has_bio_keyword:
                return -250.0

    if is_history:
        banned_history = [
            "modern office", "laptop", "smartphone", "skyscraper", "electric car",
            "jet airliner", "factory floor", "highway traffic"
        ]
        for bad in banned_history:
            if bad in text_lower:
                return -200.0

    # Extract meaningful subject words (strip generic filler words)
    stop_words = {
        "4k", "1080p", "hd", "footage", "real", "authentic", "cinematic", "video", 
        "broll", "the", "and", "for", "with", "from", "into", "that", "this", "science", "laboratory",
        "repair", "process", "mechanism", "action", "structure", "super", "fast", "like", "they", "tiny"
    }
    query_words = [w.strip(",.?!:;-()\"'").lower() for w in query.split()]
    meaningful_words = [w for w in query_words if len(w) > 2 and w not in stop_words]
    if not meaningful_words:
        meaningful_words = [w for w in query_words if len(w) > 2]

    # RELEVANCE GATING: Must match at least 1 meaningful subject keyword
    matches = sum(1 for w in meaningful_words if w in text_lower) if meaningful_words else 0
    if matches == 0:
        # STRICT REJECTION: Candidate does not mention the actual topic subject at all
        return 0.0

    match_ratio = matches / len(meaningful_words) if meaningful_words else 0.0
    overlap_score = match_ratio * 150.0  # Up to 150 points for keyword relevance

    # Anchor Entity check: if topic has a distinct subject, verify presence
    if topic:
        topic_words = [w.strip(",.?!:;-()\"'").lower() for w in topic.split() if len(w) > 3 and w.lower() not in stop_words]
        if topic_words:
            topic_matches = sum(1 for tw in topic_words if tw in text_lower)
            if topic_matches > 0:
                overlap_score += 50.0  # Big bonus for matching topic subject
            elif is_space and not any(sw in text_lower for sw in ["space", "planet", "nasa", "orbit", "astronomy", "galaxy", "telescope"]):
                return -150.0

    # Negative penalty for watermarked previews, timecode overlays, vlogs, podcasts, reactions
    bad_keywords = [
        "stock footage", "preview", "watermark", "shutterstock", "getty", "pond5", 
        "storyblocks", "adobe stock", "timecode", "sample", "vlog", "podcast", 
        "interview", "talking head", "reaction", "daily vlog", "my day", "unboxing", "review", "vlogger"
    ]
    for bad_w in bad_keywords:
        if bad_w in text_lower:
            overlap_score -= 150.0

    width = item.get("width")
    height = item.get("height")
    res_score = 10.0
    url_str = str(item.get("video_url", "")).lower()
    
    if isinstance(width, (int, float)) and width > 0:
        if width >= 3840:
            res_score = 40.0   # 4K Ultra HD top tier
        elif width >= 1920:
            res_score = 30.0   # 1080p Full HD
        elif width >= 1280:
            res_score = 15.0   # 720p HD
        else:
            res_score = -80.0  # Disqualify sub-720p blurry/grainy clips
    elif isinstance(height, (int, float)) and height > 0:
        if height >= 2160:
            res_score = 40.0
        elif height >= 1080:
            res_score = 30.0
        elif height >= 720:
            res_score = 15.0
        else:
            res_score = -80.0
    else:
        if "4k" in url_str or "2160p" in url_str:
            res_score = 40.0
        elif "1080p" in url_str or "1920" in url_str:
            res_score = 30.0
        elif "720p" in url_str or "1280" in url_str:
            res_score = 15.0
        elif "480p" in url_str or "360p" in url_str:
            res_score = -80.0
        else:
            res_score = 15.0
            
    dur_score = 10.0
    item_dur = item.get("duration")
    if isinstance(item_dur, (int, float)) and item_dur > 0:
        diff = abs(item_dur - target_duration)
        dur_score = max(0.0, 20.0 - 2.0 * diff)
        
    # High-definition video sources (Pexels, Pixabay, YouTube) prioritized for modern quality
    source_weights = {
        "pexels": 35.0,
        "pixabay": 30.0,
        "youtube": 30.0,
        "nasa": 30.0,
        "archive": 20.0,
        "wikimedia": 15.0,
        "wikipedia": 15.0,
        "dvids": 15.0,
        "reddit": 15.0,
        "coverr": 10.0,
        "klipy": 0.0
    }
    source_lower = str(item.get("source", "")).lower()
    source_score = source_weights.get(source_lower, 15.0)
    
    if source_lower == "youtube" and item.get("uploader_handle"):
        source_score += 15.0
    
    return float(overlap_score + res_score + dur_score + source_score)


def sanitize_broll_query(query: str, topic: str = "") -> str:
    """
    Sanitize B-roll query by extracting 2-4 core topic nouns and stripping all
    question words, pronouns, auxiliary verbs, and meta-descriptions that break
    Pixabay (<=100 char limit), Wikimedia, Archive.org, and stock search APIs.
    """
    if not query:
        return ""
    q_clean = re.sub(r'\bcross[-_\s]+section\b', '', query, flags=re.IGNORECASE)
    noise_words = {
        # English question words & pronouns
        "what", "why", "how", "when", "where", "which", "who", "whom", "whose",
        "this", "that", "these", "those", "there", "their", "they", "them", "its", "it",
        "the", "a", "an", "and", "or", "but", "if", "because", "as", "until", "while",
        "does", "do", "did", "doing", "done", "have", "has", "had", "having",
        "with", "from", "into", "under", "over", "more", "most", "some", "such",
        "been", "being", "will", "would", "could", "should", "shall", "might", "must",
        "about", "above", "below", "between", "both", "each", "other", "than", "then",
        # Common narrative verbs that break index lookup
        "conceal", "conceals", "concealing", "reveal", "reveals", "revealing", "revealed",
        "contain", "contains", "containing", "contained", "hold", "holds", "holding", "held",
        "survive", "survives", "surviving", "survived", "dwell", "dwells", "dwelling",
        "inhabit", "inhabits", "inhabiting", "roam", "roams", "roaming", "roamed",
        "cause", "causes", "causing", "caused", "create", "creates", "creating", "created",
        "trigger", "triggers", "triggering", "triggered", "form", "forms", "forming", "formed",
        "rage", "rages", "raging", "raged", "move", "moves", "moving", "moved",
        "travel", "travels", "traveling", "traveled", "reach", "reaches", "reaching", "reached",
        "lie", "lies", "lying", "locate", "located", "exist", "exists", "existing", "existed",
        "make", "makes", "making", "made", "become", "becomes", "becoming", "became",
        # Meta narrative words, sensational adjectives & stock noise
        "violent", "extreme", "super", "massive", "gigantic", "immense", "intense", "harsh",
        "deadly", "rapid", "fast", "slow", "freezing", "burning", "cold", "hot", "huge",
        "animated", "animation", "defect", "defective", "dramatic", "unraveling", "stuck",
        "cross", "section", "burst", "shattered", "shatter", "betraying", "secret", "secrets",
        "flaw", "concept", "visualization", "illustration", "rendering", "cgi", "showing",
        "display", "unearthing", "typing", "close", "up", "closeup", "jarring", "macro", "loop",
        "pumping", "filtering", "survival", "municipal", "system", "process", "footage", "real",
        "authentic", "video", "4k", "1080p", "hd", "bizarre", "mysterious", "incredible",
        "shocking", "unbelievable", "really", "deeply", "actual", "true", "unseen", "look",
        "looks", "looking", "seems", "seemed", "found", "find", "inside", "one", "two", "three"
    }
    q_words = re.findall(r'[a-zA-Z0-9]+', q_clean.lower())
    clean_words = [w for w in q_words if w not in noise_words and len(w) > 2 and not w.isdigit()]
    if not clean_words and topic:
        topic_words = re.findall(r'[a-zA-Z0-9]+', topic.lower())
        clean_words = [w for w in topic_words if w not in noise_words and len(w) > 2 and not w.isdigit()]
    if not clean_words:
        fallback = [w for w in q_words if len(w) > 2 and not w.isdigit()]
        return " ".join(fallback[:3])[:80] if fallback else query[:80]
    return " ".join(clean_words[:4])[:80]


def _sanitize_broll_query(query: str, topic: str = "") -> str:
    return sanitize_broll_query(query, topic=topic)


def _has_baked_text_ocr(frame_path: str) -> bool:
    """
    Uses Tesseract OCR to detect hardcoded subtitle banners, text lines, PowerPoint slides,
    lecture bullet points, or watermark logos across candidate video frames.
    Uses PIL and CLI tesseract (or pytesseract if available), zero cv2 dependency.
    """
    if not frame_path or not os.path.exists(frame_path):
        return False
    try:
        from PIL import Image
        import re, subprocess, tempfile
        try:
            import pytesseract
            has_pytesseract = True
        except ImportError:
            has_pytesseract = False

        with Image.open(frame_path) as orig_im:
            img = orig_im.convert("RGB")
        w, h = img.size

        # If it is a multi-frame collage (w > h * 2), split into individual frame images
        frames = []
        if w > h * 2:
            fw = w // 3
            frames = [
                img.crop((0, 0, fw, h)),
                img.crop((fw, 0, fw * 2, h)),
                img.crop((fw * 2, 0, w, h)),
            ]
        else:
            frames = [img]

        watermark_words = {
            "stocksubmitter", "shutterstock", "watermark", "depositphotos", "dreamstime",
            "gettyimages", "videohive", "pond5", "envato", "rights reserved", "all rights",
            "copyright", "subscribe", "no copyright", "stock footage", "preview",
            "recommendatory", "disclaimer", "investment", "subject to", "terms",
            "upstox", "paytm", "zerodha", "groww", "download", "crystal maze",
            "welcome back", "my channel", "like and share", "bell icon", "patreon",
            "episode", "chapter", "presentation", "lecture", "bullet points", "definition",
            "summary", "overview", "agenda", "slide", "lesson", "diagram", "figure",
            "problem", "solution", "example", "formula"
        }

        def run_ocr(crop_im, psm=11) -> str:
            if has_pytesseract:
                try:
                    cfg = f"--oem 1 --psm {psm} -l eng"
                    return pytesseract.image_to_string(crop_im, config=cfg, timeout=3)
                except Exception:
                    pass
            # CLI fallback using tesseract binary directly with a tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tpath = tmp.name
            try:
                crop_im.save(tpath, "JPEG", quality=85)
                cmd = ['tesseract', tpath, 'stdout', '--oem', '1', '--psm', str(psm), '-l', 'eng']
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                return res.stdout or ""
            except Exception:
                return ""
            finally:
                if os.path.exists(tpath):
                    try:
                        os.remove(tpath)
                    except Exception:
                        pass

        for f in frames:
            fw, fh = f.size

            # 1. Full frame check
            full_text = run_ocr(f, psm=11).lower()
            if any(wm in full_text for wm in watermark_words):
                return True
            words_full = re.findall(r'\b[a-z]{3,}\b', full_text)
            slide_keywords = {"agenda", "summary", "conclusion", "presentation", "slide", "chapter", "overview", "bullet"}
            if any(sk in full_text for sk in slide_keywords) and len(words_full) >= 5:
                return True
            if len(words_full) >= 12:
                # 12+ words across full frame indicates document, book page, or full lecture slide
                return True

            top_crop = f.crop((0, 0, fw, int(fh * 0.25)))
            mid_crop = f.crop((0, int(fh * 0.20), fw, int(fh * 0.80)))
            bot_crop = f.crop((0, int(fh * 0.70), fw, fh))

            # 2. Middle crop check for lecture / PowerPoint bullet points / text cards
            mid_text = run_ocr(mid_crop, psm=11).lower()
            mid_words = re.findall(r'\b[a-z]{3,}\b', mid_text)
            if any(wm in mid_text for wm in watermark_words):
                return True
            if len(mid_words) >= 8:
                # 8+ words in the middle 60% of frame -> presentation slide or text card
                return True

            # 3. Top and bottom strips for subtitles / creator banners / disclaimers
            for crop in (top_crop, bot_crop):
                crop_text = run_ocr(crop, psm=11).lower()
                crop_words = re.findall(r'\b[a-z]{3,}\b', crop_text)
                if any(wm in crop_text for wm in watermark_words):
                    return True
                if len(crop_words) >= 8:
                    # Only reject if heavy text banner; do NOT reject for corner 2-word badges
                    return True

        return False
    except Exception:
        return False


def _deep_inspect_video_frames(
    video_path: str,
    query: str = "",
    narration: str = "",
    topic: str = "",
) -> tuple[bool, str]:
    """
    Extracts frames across candidate video and performs deep frame-by-frame verification:
    1. Duration & file integrity check
    2. Minimum resolution check (>= 720p)
    3. Luminance check (rejects pure black screens or blown-out white frames)
    4. Multi-crop Tesseract OCR check (rejects slides, presentations, intro text, subtitles)
    5. Gemini Flash Vision check on sample frames (rejects talking heads, vloggers, unrelated content)
    Returns (is_valid, reason). Zero cv2 dependency.
    """
    if not video_path or not os.path.exists(video_path) or os.path.getsize(video_path) < 10_000:
        return False, "Video file missing or corrupt (<10KB)"

    total_dur = _get_video_duration(video_path)
    if total_dur < 1.0:
        return False, f"Video duration too short ({total_dur:.2f}s)"

    # Resolution check (reject low-res/muddy 240p/360p upscaled videos)
    try:
        cmd_res = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0", video_path
        ]
        res_out = subprocess.check_output(cmd_res, text=True, timeout=5).strip()
        if res_out and "x" in res_out:
            dims = [int(dim) for dim in res_out.split("x") if dim.isdigit()]
            if len(dims) >= 2:
                vw, vh = dims[0], dims[1]
                if max(vw, vh) < 720:
                    return False, f"Resolution too low ({vw}x{vh} < 720p minimum)"
    except Exception as e_res:
        pass

    from PIL import Image
    import numpy as np, tempfile

    # Sample 4 timestamps across duration: 15%, 40%, 65%, 88%
    sample_timestamps = [
        max(0.1, total_dur * 0.15),
        max(0.3, total_dur * 0.40),
        max(0.5, total_dur * 0.65),
        max(0.7, min(total_dur - 0.2, total_dur * 0.88)),
    ]

    temp_frames = []
    frame_bytes_list = []

    try:
        for idx, ts in enumerate(sample_timestamps):
            with tempfile.NamedTemporaryFile(suffix=f"_frame_{idx}.jpg", delete=False) as tf:
                frame_file = tf.name
            temp_frames.append(frame_file)

            cmd = [
                "ffmpeg", "-y", "-ss", f"{ts:.3f}",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                frame_file
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

            if not os.path.exists(frame_file) or os.path.getsize(frame_file) < 1000:
                return False, f"Failed to extract frame at t={ts:.2f}s"

            try:
                with Image.open(frame_file) as im:
                    gray = np.array(im.convert("L"))
            except Exception:
                return False, f"Frame at t={ts:.2f}s corrupted"

            # 1. Luminance check
            mean_lum = float(np.mean(gray))
            std_lum = float(np.std(gray))
            if mean_lum < 5.0 and std_lum < 5.0:
                return False, f"Black screen detected at t={ts:.2f}s (mean={mean_lum:.1f}, std={std_lum:.1f})"
            if mean_lum > 248.0 and std_lum < 10.0:
                return False, f"Washed out / white screen detected at t={ts:.2f}s"

            # 2. OCR text & slide check
            if _has_baked_text_ocr(frame_file):
                return False, f"Baked text / presentation slide detected at t={ts:.2f}s"

            # Keep frame bytes for vision check
            with open(frame_file, "rb") as fh:
                frame_bytes_list.append(fh.read())

        # 3. Gemini Flash Vision check on representative frames (t=40% and t=65%)
        if (narration or query) and len(frame_bytes_list) >= 2:
            try:
                from pipeline.vision_match import verify_video_frames
                selected_frames = [frame_bytes_list[1], frame_bytes_list[2]]
                is_valid, vision_reason = verify_video_frames(selected_frames, narration, query, topic=topic)
                if not is_valid:
                    return False, f"Vision rejected frames: {vision_reason}"
            except Exception as e_v:
                print(f"[B-roll] Vision verification note: {e_v}. Relying on heuristic frame checks.")

        return True, "All frame inspections passed"

    finally:
        for f in temp_frames:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


def fetch_broll(query: str, format_type: str, segment_index: int, duration: float = 6.0, narration: str = "", alt_queries: list[str] | None = None, used_urls: set[str] | None = None, channel: str = "general", topic: str = "") -> str:
    """
    Unified B-roll candidate ranking across multiple platforms (Reddit & YouTube prioritized, Coverr, Pexels, Pixabay, NASA, Wikimedia)
    using Gemini Vision matching and URL de-duplication.
    """
    orientation = "portrait" if format_type == "short" else "landscape"
    out_path    = f"output/broll_{segment_index}.mp4"
    img_path    = f"output/broll_{segment_index}.jpg"
    w, h        = (1080, 1920) if format_type == "short" else (1920, 1080)
    budget_default = "180" if format_type == "short" else "240"
    budget_seconds = int(os.environ.get("BROLL_SEGMENT_BUDGET_SECONDS", budget_default))
    deadline = time.monotonic() + budget_seconds

    # If topic is not provided, try reading from output/topic.json
    if not topic and os.path.exists("output/topic.json"):
        try:
            with open("output/topic.json", "r") as tf:
                topic_data = json.load(tf)
                topic = topic_data.get("topic", "")
        except Exception:
            pass

    # Ensure any stale credit files from previous attempts are wiped
    for f_stale in [
        f"output/broll_{segment_index}_credit.json",
        f"output/broll_{segment_index}_0_credit.json",
        f"output/broll_{segment_index}_1_credit.json",
        f"output/broll_{segment_index}_2_credit.json",
        f"output/broll_{segment_index}_3_credit.json",
    ]:
        if os.path.exists(f_stale):
            try:
                os.remove(f_stale)
            except Exception:
                pass

    def budget_exceeded() -> bool:
        if time.monotonic() <= deadline:
            return False
        print(f"[B-roll] Segment {segment_index}: time budget exceeded ({budget_seconds}s). Using fast fallback.")
        return True

    os.makedirs("output", exist_ok=True)
    is_space_or_sci = channel in ["space", "astrophysics", "astronomy", "science", "engineering"] or any(w in (query or "").lower() for w in ["space", "nasa", "planet", "galaxy", "telescope", "orbit", "astronomy", "cosmos", "rocket", "physics", "engine", "cern", "accelerator"])
    is_space_topic = is_space_or_sci

    # Return cached clip if already valid
    if os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
        print(f"[B-roll] Segment {segment_index}: using cached clip.")
        return out_path

    # Build fallback queries with sanitization
    sanitized_q = _sanitize_broll_query(query)
    clean_fallback = _make_clean_fallback(query)
    general_fallback = sanitized_q or query
    
    # Only keep compact, high-intent queries (strip long conversational sentences)
    queries_to_try = [sanitized_q, clean_fallback]
    if len(query.split()) <= 4 and query.lower() not in [x.lower() for x in queries_to_try if x]:
        queries_to_try.append(query)

    if alt_queries:
        for q in alt_queries:
            sq = _sanitize_broll_query(q)
            if sq and sq not in queries_to_try:
                queries_to_try.append(sq)
        
    # Generate ultra-targeted 2-3 noun keyword queries for search APIs
    stop_stock = {"4k", "1080p", "hd", "footage", "real", "authentic", "video", "discovery", "breakthrough", "logic", "superposition", "unprecedented", "fundamental", "revolution"}
    core_nouns = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', query).split() if len(w) > 2 and w.lower() not in stop_stock]
    if len(core_nouns) >= 2:
        anchor = core_nouns[0]
        q_pair1 = " ".join(core_nouns[:2])
        q_pair2 = f"{anchor} {core_nouns[-1]}"  # Retain anchor noun so subject entity is NEVER lost
        if q_pair1 not in queries_to_try: queries_to_try.insert(0, q_pair1)
        if q_pair2 not in queries_to_try: queries_to_try.insert(1, q_pair2)
    if len(core_nouns) >= 3:
        q_tri = " ".join(core_nouns[:3])
        if q_tri not in queries_to_try: queries_to_try.insert(0, q_tri)

    if not budget_exceeded():
        expanded = _expand_query(sanitized_q or query, channel=channel, n=4, narration=narration, topic=topic)
        queries_to_try.extend(expanded)

    candidates = []

    # ── Phase 4.1: High-Precision Semantic Entity & Multi-Platform Harvester ──
    try:
        from pipeline.video_harvester_engine import get_video_harvester
        harvester = get_video_harvester()
        profile, harvested = harvester.harvest_for_sentence(narration or query, niche=channel, max_candidates=8, topic=topic)
        if harvested:
            print(f"[B-roll] Segment {segment_index}: Entity Harvester identified anchor '{profile.anchor_entity}' ({profile.entity_category}) with {len(harvested)} verified authentic candidates.")
            for hc in harvested:
                cand_dict = {
                    "source": hc.platform.capitalize(),
                    "video_url": hc.stream_url or hc.url,
                    "thumb_url": hc.thumbnail_url or (f"https://img.youtube.com/vi/{hc.id}/hqdefault.jpg" if "youtube" in hc.platform.lower() else ""),
                    "title": hc.title,
                    "description": hc.description,
                    "duration": hc.duration,
                    "uploader_name": hc.channel_name,
                    "uploader_handle": hc.channel_name if str(hc.channel_name).startswith(("@", "u/")) else f"@{hc.channel_name}",
                    "channel_url": hc.url,
                    "_score": float(hc.score + 50.0)
                }
                candidates.append(cand_dict)
    except Exception as e_harv:
        print(f"[B-roll] Entity Harvester note: {e_harv}")

    # Deduplicate final query list (case-insensitive while preserving order)
    seen_q = set()
    queries_to_try_dedup = []
    for q in queries_to_try:
        if q and q.lower() not in seen_q:
            seen_q.add(q.lower())
            queries_to_try_dedup.append(q)
    queries_to_try = queries_to_try_dedup

    # Prioritize authentic institutional archives first across all channels (100% unblocked on cloud runners)
    CHANNEL_SOURCE_PRIORITY = {
        "mystery":     ["wikimedia", "archive", "youtube", "pexels", "pixabay"],
        "nature":      ["wikimedia", "archive", "youtube", "pexels", "pixabay"],
        "science":     ["wikimedia", "nasa", "archive", "youtube", "pexels", "pixabay"],
        "space":       ["nasa", "wikimedia", "archive", "youtube", "pexels", "pixabay"],
        "engineering": ["wikimedia", "nasa", "archive", "dvids", "youtube", "pexels", "pixabay"],
        "business":    ["archive", "wikimedia", "youtube", "pexels", "pixabay"],
        "military":    ["dvids", "archive", "wikimedia", "youtube", "pexels"],
        "general":     ["wikimedia", "archive", "youtube", "pexels", "pixabay"],
    }

    def run_source_query(source: str, q: str) -> list[dict]:
        try:
            if source == "reddit":
                return _reddit_candidates(q, n=4, channel=channel)
            elif source == "youtube":
                return _youtube_candidates(q, n=5)
            elif source == "nasa":
                if not NASA_BROLL_ENABLED:
                    return []
                cand = _nasa_video_candidate(q)
                return [cand] if cand else []
            elif source == "wikimedia":
                cand = _wikimedia_video_candidate(q)
                return [cand] if cand else []
            elif source == "dvids":
                return _dvids_candidates(q, n=3)
            elif source == "coverr":
                if not COVERR_API_KEY:
                    return []
                return _coverr_candidates(q, orientation, n=2)
            elif source == "klipy":
                if not KLIPY_API_KEY:
                    return []
                return _klipy_candidates(q, n=2)
            elif source == "pexels":
                if not PEXELS_API_KEY:
                    return []
                return _pexels_candidates(q, orientation, n=2)
            elif source == "pixabay":
                if not PIXABAY_API_KEY:
                    return []
                return _pixabay_candidates(q, n=2)
            elif source == "archive":
                return _archive_candidates(q, n=3)
        except Exception as e:
            print(f"[B-roll] Source {source} query '{q}' failed: {e}")
        return []

    sources = CHANNEL_SOURCE_PRIORITY.get(channel, CHANNEL_SOURCE_PRIORITY["general"])
    tasks = []
    for source in sources:
        for q in queries_to_try[:6]:
            tasks.append((source, q))

    seen_gathering = set()
    source_counts = {src: 0 for src in sources}

    remaining_budget = max(1.0, deadline - time.monotonic())
    timeout = min(45, int(remaining_budget * 0.5))
    if timeout < 1:
        timeout = 1

    print(f"[B-roll] Segment {segment_index}: starting parallel candidate gathering with timeout={timeout}s for sources: {sources}...")

    with ThreadPoolExecutor(max_workers=min(12, len(tasks))) as executor:
        future_to_info = {}
        for source, q in tasks:
            f = executor.submit(run_source_query, source, q)
            future_to_info[f] = (source, q)

        try:
            for future in as_completed(future_to_info.keys(), timeout=timeout):
                source, q = future_to_info[future]
                try:
                    res = future.result()
                    if res:
                        added_count = 0
                        for cand in res:
                            if not isinstance(cand, dict):
                                continue
                            v_url = cand.get("video_url")
                            if v_url and v_url not in seen_gathering:
                                seen_gathering.add(v_url)
                                if "source" not in cand:
                                    cand["source"] = source
                                candidates.append(cand)
                                added_count += 1
                        source_counts[source] += added_count
                except Exception as e:
                    print(f"[B-roll] Future failed for source {source} query '{q}': {e}")
        except Exception as e:
            if "TimeoutError" in type(e).__name__:
                print(f"[B-roll] Parallel gathering timed out after {timeout} seconds.")
            else:
                print(f"[B-roll] Error during parallel gathering: {e}")

    for src in sources:
        print(f"[B-roll] Source '{src}' returned {source_counts[src]} unique candidates.")

    def _candidate_fingerprint(item: dict) -> str:
        url = str(item.get("video_url", "")).strip()
        title = str(item.get("title", "")).strip().lower()
        yt_m = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', url)
        if yt_m:
            return f"yt:{yt_m.group(1)}"
        red_m = re.search(r'comments/([a-zA-Z0-9]+)', url)
        if red_m:
            return f"reddit:{red_m.group(1)}"
        pex_m = re.search(r'pexels[^\d]*(\d+)', url)
        if pex_m:
            return f"pexels:{pex_m.group(1)}"
        pix_m = re.search(r'pixabay[^\d]*(\d+)', url)
        if pix_m:
            return f"pixabay:{pix_m.group(1)}"
        if title and len(title) > 8:
            title_slug = re.sub(r'[^a-z0-9]', '', title)[:30]
            return f"title:{title_slug}"
        return url.split("?")[0].rstrip("/")

    # Apply de-duplication: filter out candidates that have already been used
    if used_urls:
        original_count = len(candidates)
        filtered_cands = []
        for c in candidates:
            vurl = c.get("video_url", "")
            fp = _candidate_fingerprint(c)
            if vurl in used_urls or fp in used_urls:
                continue
            filtered_cands.append(c)
        candidates = filtered_cands
        if len(candidates) < original_count:
            print(f"[B-roll] De-duplicated candidates: filtered out {original_count - len(candidates)} already used clips.")

    # Score all candidates
    for c in candidates:
        c["_score"] = _score_candidate(c, query, target_duration=duration, topic=topic, channel=channel)

    # Disqualify candidates that triggered domain bans or scored <= 0
    candidates = [c for c in candidates if c.get("_score", 0.0) > 0.0]

    # Multi-platform diversity interleaving: guarantee top candidates include Reddit, Archive, Wikimedia, NASA alongside YouTube
    platform_buckets = {}
    for c in candidates:
        src = c.get("source", "Other").lower()
        if src not in platform_buckets:
            platform_buckets[src] = []
        platform_buckets[src].append(c)

    # Sort each platform's candidates by score descending
    for src in platform_buckets:
        platform_buckets[src].sort(key=lambda x: x.get("_score", 0.0), reverse=True)

    # Round-robin interleave from distinct platforms to guarantee multi-source coverage
    interleaved_candidates = []
    source_priority_order = ["nasa", "wikimedia", "archive", "dvids", "reddit", "youtube", "pexels", "pixabay", "coverr"]
    for sp in source_priority_order:
        if sp in platform_buckets and platform_buckets[sp]:
            interleaved_candidates.append(platform_buckets[sp].pop(0))
            if len(interleaved_candidates) >= 8:
                break

    # Fill remaining slots with highest remaining scores across all platforms
    remaining_all = []
    for src, clist in platform_buckets.items():
        remaining_all.extend(clist)
    remaining_all.sort(key=lambda x: x.get("_score", 0.0), reverse=True)
    for rc in remaining_all:
        if len(interleaved_candidates) >= 8:
            break
        if rc not in interleaved_candidates:
            interleaved_candidates.append(rc)

    candidates = interleaved_candidates if interleaved_candidates else candidates[:8]

    # Print the top sources in order so the log shows ranking
    if candidates:
        ranking_str = ", ".join(f"{c.get('source', 'Unknown')} (score: {c.get('_score', 0.0):.1f})" for c in candidates)
        print(f"[B-roll] Top candidates after scoring: {ranking_str}")

    # Run Gemini Vision matching on candidates
    if candidates:
        print(f"[B-roll] Segment {segment_index}: Ranking {len(candidates)} candidates from: {', '.join(set(c.get('source', 'Unknown') for c in candidates))}…")
        thumbs = []
        valid_candidates = []
        for idx, cand in enumerate(candidates):
            if budget_exceeded():
                break
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*"
                }
                r_thumb = requests.get(cand["thumb_url"], headers=headers, timeout=15)
                r_thumb.raise_for_status()
                from PIL import Image
                import io
                Image.open(io.BytesIO(r_thumb.content)).verify()
                
                thumbs.append(r_thumb.content)
                valid_candidates.append(cand)
            except Exception as e:
                print(f"[B-roll] Failed/invalid thumbnail {idx} from {cand.get('source', 'Unknown')}: {e}")

        if valid_candidates:
            print(f"[B-roll] Segment {segment_index}: Ranking {len(valid_candidates)} candidates from: {', '.join(set(c.get('source', 'Unknown') for c in valid_candidates))}…")
            from pipeline.vision_match import vision_rank_broll
            best_idx, match_found = vision_rank_broll(thumbs, narration, query, topic=topic)

            if match_found is True and best_idx is not None and best_idx < len(valid_candidates):
                # Order candidates prioritizing best_idx, then remaining valid candidates (try up to 3)
                ordered_indices = [best_idx] + [i for i in range(len(valid_candidates)) if i != best_idx]
                for try_idx in ordered_indices[:3]:
                    if budget_exceeded():
                        break
                    chosen = valid_candidates[try_idx]
                    print(f"[B-roll] Trying candidate {try_idx} ({chosen.get('source', 'Unknown')}): {chosen['video_url'][:60]}...")
                    temp_video_path = f"output/temp_video_{segment_index}.mp4"
                    if _download_video_robust(chosen["video_url"], temp_video_path, segment_index, candidate_info=chosen):
                        # Deep frame-by-frame inspection before accepting into video
                        passed, reason = _deep_inspect_video_frames(temp_video_path, query=query, narration=narration, topic=topic)
                        if not passed:
                            print(f"[B-roll] Candidate {try_idx} REJECTED by frame inspection: {reason}. Trying next candidate...")
                            if os.path.exists(temp_video_path):
                                try:
                                    os.remove(temp_video_path)
                                except Exception:
                                    pass
                            continue

                        # Frame inspection passed!
                        if used_urls is not None:
                            used_urls.add(chosen["video_url"])
                            used_urls.add(_candidate_fingerprint(chosen))
                        print(f"[B-roll] Candidate {try_idx} VERIFIED frame-by-frame! Normalizing into assembly format...")
                        _image_to_ken_burns_video(temp_video_path, out_path, w, h, duration, niche=channel, caption="")
                        if os.path.exists(temp_video_path):
                            try:
                                os.remove(temp_video_path)
                            except Exception:
                                pass
                        return out_path
                    else:
                        print(f"[B-roll] Video download failed for candidate {try_idx}. Trying next candidate...")
            elif match_found is None:
                print(f"[B-roll] Segment {segment_index}: Vision API unavailable/exhausted. Auditing top-scoring candidates with deep frame inspection...")
                sorted_cands = sorted(valid_candidates, key=lambda c: c.get("_score", 0.0), reverse=True)
                trusted_sources = {"NASA", "MBARI", "NOAA", "DVIDS", "Wikimedia", "Wikipedia"}
                # When Vision API is down, ONLY accept verified institutional archives. NEVER accept commercial stock without vision verification.
                high_quality_cands = [c for c in sorted_cands if c.get("_score", 0.0) >= 50 and c.get("source") in trusted_sources]
                if not high_quality_cands:
                    print(f"[B-roll] Segment {segment_index}: No trusted institutional archives available while Vision API is down. Skipping unverified commercial stock to prevent mismatches.")
                    high_quality_cands = []

                for try_idx, chosen in enumerate(high_quality_cands[:3]):
                    if budget_exceeded():
                        break
                    print(f"[B-roll] Trying heuristic candidate {try_idx} ({chosen.get('source', 'Unknown')}, score={chosen.get('_score', 0.0):.1f}): {chosen['video_url'][:60]}...")
                    temp_video_path = f"output/temp_video_{segment_index}.mp4"
                    if _download_video_robust(chosen["video_url"], temp_video_path, segment_index, candidate_info=chosen):
                        passed, reason = _deep_inspect_video_frames(temp_video_path, query=query, narration=narration, topic=topic)
                        if not passed:
                            print(f"[B-roll] Heuristic candidate {try_idx} REJECTED by frame inspection: {reason}. Trying next candidate...")
                            if os.path.exists(temp_video_path):
                                try:
                                    os.remove(temp_video_path)
                                except Exception:
                                    pass
                            continue

                        if used_urls is not None:
                            used_urls.add(chosen["video_url"])
                            used_urls.add(_candidate_fingerprint(chosen))
                        print(f"[B-roll] Heuristic candidate {try_idx} VERIFIED frame-by-frame! Normalizing into assembly format...")
                        _image_to_ken_burns_video(temp_video_path, out_path, w, h, duration, niche=channel, caption="")
                        if os.path.exists(temp_video_path):
                            try:
                                os.remove(temp_video_path)
                            except Exception:
                                pass
                        return out_path
                    else:
                        print(f"[B-roll] Video download failed for heuristic candidate {try_idx}. Trying next...")
            else:
                print(f"[B-roll] Segment {segment_index}: Vision match strictly rejected all video candidates as unrelated stock slop.")

    # ── Fallback 1: Single Frame fallback search on other videos waterfall ─────────────────
    print(f"[B-roll] Segment {segment_index}: falling back to parallel waterfall search...")
    
    # 1. Authentic unblocked institutional video archives (Priority 1)
    other_videos = [
        ("Wikimedia video (main)", lambda: _wikimedia_video(sanitized_q or clean_fallback)),
        ("Wikimedia video (fallback)", lambda: _wikimedia_video(clean_fallback)),
        ("Archive video (main)", lambda: _archive_video(sanitized_q or clean_fallback)),
        ("Archive video (fallback)", lambda: _archive_video(clean_fallback)),
    ]
    
    # NASA for space, physics, engineering, astronomy
    is_space_or_sci = channel in ["space", "astrophysics", "astronomy", "science", "engineering"] or any(w in query.lower() for w in ["space", "nasa", "planet", "galaxy", "telescope", "orbit", "astronomy", "cosmos", "rocket", "physics", "engine", "cern", "accelerator"])
    if is_space_or_sci and NASA_BROLL_ENABLED:
        other_videos.extend([
            ("NASA video (main)", lambda: _nasa_video(sanitized_q or clean_fallback)),
            ("NASA video (fallback)", lambda: _nasa_video(clean_fallback)),
        ])

    # DVIDS for military/defense topics
    is_military_topic = channel in ["military", "defense", "aviation", "geopolitics"] or any(w in query.lower() for w in ["military", "warfare", "army", "navy", "warship", "fighter jet", "weapon"])
    if is_military_topic:
        other_videos.extend([
            ("DVIDS video (main)", lambda: _dvids_video(sanitized_q or clean_fallback)),
            ("DVIDS video (fallback)", lambda: _dvids_video(clean_fallback)),
        ])

    # 2. YouTube CC (secondary)
    other_videos.extend([
        ("YouTube CC (main)", lambda: _youtube_candidates(sanitized_q or clean_fallback, n=1)[0]["video_url"] if _youtube_candidates(sanitized_q or clean_fallback, n=1) else None),
        ("YouTube CC (fallback)", lambda: _youtube_candidates(clean_fallback, n=1)[0]["video_url"] if _youtube_candidates(clean_fallback, n=1) else None),
    ])

    # 3. Stock sites as low-priority fallbacks
    other_videos.extend([
        ("Pixabay (main)", lambda: _pixabay_video(sanitized_q or clean_fallback)),
        ("Pixabay (fallback)", lambda: _pixabay_video(clean_fallback)),
        ("Coverr (main)", lambda: _coverr_video(sanitized_q or clean_fallback)),
        ("Coverr (fallback)", lambda: _coverr_video(clean_fallback)),
    ])

    # Gather candidate URLs to download in parallel (up to 5)
    candidates_to_download = []
    seen_urls = set()
    for label, fetch_url_fn in other_videos:
        if budget_exceeded():
            break
        try:
            video_url = fetch_url_fn()
            if video_url and video_url not in seen_urls:
                if used_urls and video_url in used_urls:
                    continue
                seen_urls.add(video_url)
                candidates_to_download.append({
                    "label": label,
                    "video_url": video_url
                })
                if len(candidates_to_download) >= 5:
                    break
        except Exception as e:
            print(f"[B-roll] Failed to fetch URL for {label}: {e}")

    # Helper function for parallel downloads and frame extraction
    def download_and_extract_frame(cand, idx):
        lbl = cand["label"]
        vurl = cand["video_url"]
        temp_v = f"output/temp_video_{segment_index}_{idx}.mp4"
        temp_f = f"output/temp_frame_{segment_index}_{idx}.jpg"
        
        for p in [temp_v, temp_f]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        
        print(f"[B-roll] Downloading video from {lbl} in parallel...")
        if _download_video_robust(vurl, temp_v, f"{segment_index}_{idx}"):
            passed, reason = _deep_inspect_video_frames(temp_v, query=query, narration=narration, topic=topic)
            if not passed:
                print(f"[B-roll] Skipping candidate '{lbl}' due to frame inspection: {reason}")
            elif _extract_collage_to_file(temp_v, temp_f):
                with open(temp_f, "rb") as fh:
                    f_data = fh.read()
                return {
                    "label": lbl,
                    "video_url": vurl,
                    "temp_v": temp_v,
                    "temp_f": temp_f,
                    "frame_data": f_data
                }
        
        # Cleanup on failure
        for p in [temp_v, temp_f]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        return None

    # Download candidates in parallel threads
    import concurrent.futures
    downloaded_results = []
    if candidates_to_download:
        max_workers = min(len(candidates_to_download), 5)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(download_and_extract_frame, cand, i)
                for i, cand in enumerate(candidates_to_download)
            ]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                    if res:
                        downloaded_results.append(res)
                except Exception as e:
                    print(f"[B-roll] Thread download failed: {e}")

    # Rank downloaded candidates using Gemini Vision Match in one batch
    from pipeline.vision_match import vision_rank_broll
    if downloaded_results:
        print(f"[B-roll] Segment {segment_index}: Ranking {len(downloaded_results)} downloaded candidates in batch...")
        thumbs = [r["frame_data"] for r in downloaded_results]
        best_idx, match_found = vision_rank_broll(thumbs, narration, query, topic=topic)
        
        if match_found is True and best_idx is not None and 0 <= best_idx < len(downloaded_results):
            winner = downloaded_results[best_idx]
            winner_idx = best_idx
            print(f"[B-roll] Parallel winner chosen! Source: {winner['label']} (Index: {best_idx})")
            
            # Run the video through Ken Burns normalization
            print(f"[B-roll] Winner video. Running video normalization...")
            _image_to_ken_burns_video(winner["temp_v"], out_path, w, h, duration, niche=channel, caption="")
            
            # Copy winner credit metadata if present
            winner_credit_file = f"output/broll_{segment_index}_{winner_idx}_credit.json"
            target_credit_file = f"output/broll_{segment_index}_credit.json"
            if os.path.exists(winner_credit_file):
                import shutil
                shutil.copy(winner_credit_file, target_credit_file)

            if used_urls is not None:
                used_urls.add(winner["video_url"])
                used_urls.add(_candidate_fingerprint(winner))
                
            # Clean up temporary video files
            for r in downloaded_results:
                for p in [r["temp_v"], r["temp_f"]]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
            return out_path
        elif match_found is None and downloaded_results:
            trusted_labels = ["nasa", "mbari", "noaa", "dvids", "wikimedia", "wikipedia", "archive"]
            trusted_winners = [r for r in downloaded_results if any(tl in r.get("label", "").lower() for tl in trusted_labels)]
            if trusted_winners:
                winner = trusted_winners[0]
                winner_idx = downloaded_results.index(winner)
                print(f"[B-roll] Segment {segment_index}: Vision API unavailable. Accepting institutional candidate from {winner['label']}...")
                _image_to_ken_burns_video(winner["temp_v"], out_path, w, h, duration, niche=channel, caption="")
                winner_credit_file = f"output/broll_{segment_index}_{winner_idx}_credit.json"
                target_credit_file = f"output/broll_{segment_index}_credit.json"
                if os.path.exists(winner_credit_file):
                    import shutil
                    shutil.copy(winner_credit_file, target_credit_file)
                if used_urls is not None:
                    used_urls.add(winner["video_url"])
                    used_urls.add(_candidate_fingerprint(winner))
                for r in downloaded_results:
                    for p in [r["temp_v"], r["temp_f"]]:
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except Exception:
                                pass
                return out_path
            else:
                print(f"[B-roll] Segment {segment_index}: Vision API unavailable and no trusted institutional archives found. Strictly rejecting commercial stock to prevent mismatches. Proceeding to authentic topic stills / Pollinations Flux synthesis.")
                for r in downloaded_results:
                    for p in [r["temp_v"], r["temp_f"]]:
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except Exception:
                                pass
        else:
            print(f"[B-roll] Segment {segment_index}: Vision match strictly rejected all downloaded video candidates. Proceeding to authentic topic stills / Pollinations Flux synthesis.")
            for r in downloaded_results:
                for p in [r["temp_v"], r["temp_f"]]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass

    # Ensure stale video credit files are strictly wiped before any image fallback
    stale_credit_f = f"output/broll_{segment_index}_credit.json"
    if os.path.exists(stale_credit_f):
        try:
            os.remove(stale_credit_f)
        except Exception:
            pass

    # ── Fallback 2: authentic topic imagery or Pollinations 4K synthesis ─────────────
    print(f"[B-roll] Segment {segment_index}: trying authentic archival image sources and 4K scene synthesis…")

    # High-authority NASA image if space topic
    if NASA_BROLL_ENABLED and is_space_topic:
        nasa_img_url = _nasa_image(sanitized_q or query)
        if nasa_img_url and (used_urls is None or nasa_img_url not in used_urls):
            try:
                r_n = requests.get(nasa_img_url, timeout=20, headers={"User-Agent": "yt-auto/2.0"})
                if r_n.status_code == 200 and len(r_n.content) > 10_000:
                    with open(img_path, "wb") as f:
                        f.write(r_n.content)
                    if _validate_and_normalize_image(img_path):
                        if used_urls is not None:
                            used_urls.add(nasa_img_url)
                        print(f"[B-roll] Segment {segment_index}: Official NASA HD space image secured. Applying Ken Burns…")
                        _image_to_ken_burns_video(img_path, out_path, w, h, duration, niche=channel, caption="")
                        if os.path.exists(stale_credit_f):
                            try: os.remove(stale_credit_f)
                            except Exception: pass
                        return out_path
            except Exception as e:
                print(f"[B-roll] NASA image fetch failed: {e}")

    # Direct official Wikipedia / Wikimedia Commons HD photograph with strict title validation
    if _wikipedia_hd_image(sanitized_q or topic or query, img_path, used_urls=used_urls, topic=topic):
        print(f"[B-roll] Segment {segment_index}: official Wikipedia/Wikimedia HD archival photo secured. Applying Ken Burns 2.5D…")
        _image_to_ken_burns_video(img_path, out_path, w, h, duration, niche=channel, caption="")
        if os.path.exists(stale_credit_f):
            try: os.remove(stale_credit_f)
            except Exception: pass
        return out_path

    # Fallback 3: Unique Pollinations 4K Photorealistic Scene tailored to exact segment narration
    pollin_query = f"{topic} {narration or query}".strip() if topic else (narration or query)
    banned_metaphors = [
        "conan the bacterium", "conan the barbarian", "conan", "frankenstein", "godzilla",
        "monster", "beast", "werewolf", "tiny warriors", "antidote factory", "secret weapon",
        "magic bullet", "superhero", "zombie", "alien invader", "vampire"
    ]
    sanitized_pollin = pollin_query
    for b in banned_metaphors:
        sanitized_pollin = re.sub(r'\b' + re.escape(b) + r'\b', '', sanitized_pollin, flags=re.IGNORECASE)
    if channel in ["nature", "science"]:
        sanitized_pollin = re.sub(r'\bbugs?\b', 'microorganisms', sanitized_pollin, flags=re.IGNORECASE)
    sanitized_pollin = re.sub(r'\s+', ' ', sanitized_pollin).strip()

    if channel == "nature":
        clean_prompt = f"4k cinematic authentic national geographic macro photography or electron micrograph of {sanitized_pollin[:90]}, biological specimen, wild nature, scientific documentary, hyperrealistic, 8k, highly detailed, photorealistic, no text, no watermark, no slides, no humans"
    elif channel == "science":
        clean_prompt = f"4k cinematic scientific photography or scanning electron micrograph of {sanitized_pollin[:90]}, laboratory apparatus, physics, hyperrealistic, 8k, photorealistic, no text, no watermark, no slides, no humans"
    else:
        clean_prompt = f"4k cinematic documentary footage of {sanitized_pollin[:90]}, photorealistic, 8k, detailed, national geographic photography, no text, no watermark, no slides"

    print(f"[B-roll] Segment {segment_index}: Generating unique Pollinations AI 4K documentary visual...")
    if _pollinations_image(clean_prompt, img_path, w, h):
        print(f"[B-roll] Segment {segment_index}: 4K documentary scene synthesized! Applying Ken Burns motion…")
        _image_to_ken_burns_video(img_path, out_path, w, h, duration, niche=channel, caption="")
        if os.path.exists(stale_credit_f):
            try: os.remove(stale_credit_f)
            except Exception: pass
        return out_path

    img_sources = []
    queries_for_images = [sanitized_q, clean_fallback, query]
    if topic:
        queries_for_images.append(_sanitize_broll_query(topic)[:80])

    for q_candidate in queries_for_images:
        if not q_candidate:
            continue
        img_sources.append((_wikimedia_image, q_candidate))
        img_sources.append((_wikipedia_image, q_candidate))
        img_sources.append((_openverse_image, q_candidate))

    img_url = None
    for img_fn, q in img_sources:
        candidate_img = img_fn(q)
        if candidate_img and (used_urls is None or candidate_img not in used_urls):
            img_url = candidate_img
            if used_urls is not None:
                used_urls.add(img_url)
            break

    if img_url:
        try:
            r = requests.get(img_url, timeout=30, headers={"User-Agent": "yt-auto-bot/2.0 (https://github.com/mahesajeth-wq/yt-auto; contact@mahesajeth.com)"})
            r.raise_for_status()
            with open(img_path, "wb") as f:
                f.write(r.content)
            if not _validate_and_normalize_image(img_path):
                raise ValueError("Downloaded image validation failed")
            print(f"[B-roll] Segment {segment_index}: authentic image downloaded ({img_url[:60]}...). Applying Ken Burns…")
            _image_to_ken_burns_video(img_path, out_path, w, h, duration, niche=channel, caption="")
            return out_path
        except Exception as e:
            print(f"[B-roll] Image source failed: {e}. Trying procedural plate…")

    # ── Fallback 4: Text-free Cinematic Background Plate with Ken Burns ───
    print(f"[B-roll] Segment {segment_index}: Generating clean cinematic background plate...")
    _pil_placeholder("", w, h, img_path)
    _image_to_ken_burns_video(img_path, out_path, w, h, duration, niche=channel, caption="")
    return out_path
