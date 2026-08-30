"""
reddit_engine.py - Advanced Reddit Video Scraping & Semantic Footage Discovery Engine

Bypasses Reddit bot/Cloudflare walls by combining:
1. PullPush, Arctic Shift & Redlib Public JSON Stream Extractors
2. Semantic Gemini-Grounded Reddit Intelligence (discovers exact named eyewitness clips & viral recordings)
3. Direct v.redd.it DASH High-Definition Muxing (1080p/720p H.264 + AAC audio direct copy mux)
4. Subreddit Domain Routing Matrix across mysteries, nature, engineering, and science.
"""

import os
import re
import json
import time
import requests
import urllib.parse
import subprocess
from typing import List, Dict, Optional, Tuple
from pipeline.config import GEMINI_FLASH
from pipeline.gemini import GeminiClient, _robust_json_loads

# Domain routing matrix mapping content niches to premier video subreddits
NICHE_SUBREDDITS = {
    "mystery": [
        "Bigfoot", "Cryptozoology", "HighStrangeness", "UFOs", "Ghosts",
        "Humanoidencounters", "StrangeEarth", "Paranormal", "Damnthatsinteresting"
    ],
    "nature": [
        "NatureIsFuckingLit", "Damnthatsinteresting", "interestingasfuck",
        "marinebiology", "wildlifephotography", "Oceanlinerporn", "deepseacreatures"
    ],
    "science": [
        "space", "astrophotography", "science", "physicsgifs", "chemicalreactiongifs",
        "Damnthatsinteresting", "interestingasfuck"
    ],
    "engineering": [
        "engineeringporn", "InfrastructurePorn", "MachinePorn", "specializedtools",
        "aviation", "Damnthatsinteresting", "megaprojects"
    ],
    "general": [
        "Damnthatsinteresting", "interestingasfuck", "BeAmazed", "NextFuckingLevel"
    ]
}

REDLIB_INSTANCES = [
    "https://redlib.freedit.eu",
    "https://safereddit.com",
    "https://redlib.catsarch.com",
    "https://redlib.tux.pizza"
]


class RedditVideoEngine:
    def __init__(self):
        self.client = GeminiClient()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })

    def discover_community_footage(self, topic: str, niche: str = "mystery", max_items: int = 4) -> List[Dict]:
        """
        Queries Gemini with Google Grounding to discover the exact authentic eyewitness clips,
        viral user video recordings, and documented phenomena discussed in top subreddits.
        """
        subreddits = NICHE_SUBREDDITS.get(niche, NICHE_SUBREDDITS["general"])
        sub_list_str = ", ".join(f"r/{s}" for s in subreddits[:5])
        
        prompt = f"""You are a specialized multimedia archival researcher.
Topic: '{topic}'
Niche / Channel: '{niche}'
Target Subreddit Communities: {sub_list_str}

Identify up to {max_items} specific, famous, authentic, or highly-discussed real-world video recordings, eyewitness captures, or raw camera footage relevant to this topic that are shared on Reddit.

For each piece of footage, return:
- "footage_name": Specific title or identifying name of the clip (e.g. 'Paul Freeman 1994 Bigfoot Footage', 'Calgary 2014 Stabilized Footage', 'MBARI Magnapinna Squid 4K ROV Dive')
- "search_query": Exact optimized 4K/1080p query to download the master footage on YouTube/Reddit/Archive (e.g. 'Paul Freeman Bigfoot footage 1994 1080p', 'MBARI Magnapinna Squid 4k dive')
- "attribution_tag": Creator handle or community source (e.g. 'r/Bigfoot', 'r/NatureIsFuckingLit', '@MBARIvideo')
- "context": Visual summary of what appears in the video.

Return ONLY a strict JSON array of objects with keys: "footage_name", "search_query", "attribution_tag", "context"."""

        try:
            resp = self.client.generate_text(prompt, model=GEMINI_FLASH)
            data = _robust_json_loads(resp)
            if isinstance(data, list):
                print(f"[RedditEngine] Discovered {len(data)} authentic community footage titles for '{topic}'.")
                return data[:max_items]
        except Exception as e:
            print(f"[RedditEngine] Community footage discovery note: {e}")
            
        # Fallback to direct query expansion
        return [
            {
                "footage_name": f"{topic} Real Footage",
                "search_query": f"{topic} real authentic footage 4k",
                "attribution_tag": f"r/{subreddits[0]}",
                "context": "Documentary raw footage"
            }
        ]

    def search_pullpush_videos(self, query: str, niche: str = "general", n: int = 4) -> List[Dict]:
        """Queries open PullPush Reddit archive API for direct video posts."""
        candidates = []
        clean_q = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
        if not clean_q:
            return []
            
        subreddits = NICHE_SUBREDDITS.get(niche, NICHE_SUBREDDITS["general"])
        sub_param = ",".join(subreddits[:3])
        
        try:
            url = f"https://api.pullpush.io/reddit/search/submission/?q={urllib.parse.quote(clean_q)}&subreddit={sub_param}&is_video=true&size=15"
            r = self.session.get(url, timeout=5)
            if r.status_code == 200:
                items = r.json().get("data", [])
                seen = set()
                for it in items:
                    media = it.get("media") or {}
                    r_vid = media.get("reddit_video") if isinstance(media, dict) else None
                    f_url = r_vid.get("fallback_url") if r_vid else None
                    if not f_url and it.get("is_video") and it.get("url", "").endswith(".mp4"):
                        f_url = it.get("url")
                    if not f_url or f_url in seen:
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
                            
                    candidates.append({
                        "source": "Reddit",
                        "video_url": f_url,
                        "thumb_url": thumb,
                        "title": title,
                        "duration": float(r_vid.get("duration", 10.0)) if r_vid else 10.0,
                        "uploader_name": f"r/{sub}",
                        "uploader_handle": f"u/{author} (r/{sub})",
                        "channel_url": f"https://reddit.com/r/{sub}",
                        "score": it.get("score", 0)
                    })
                    if len(candidates) >= n:
                        break
        except Exception as e:
            print(f"[RedditEngine] PullPush query note: {e}")
            
        return candidates

    def search_redlib_videos(self, query: str, niche: str = "general", n: int = 4) -> List[Dict]:
        """Queries Redlib mirror network for Reddit video posts."""
        candidates = []
        subreddits = NICHE_SUBREDDITS.get(niche, NICHE_SUBREDDITS["general"])
        sub = subreddits[0] if subreddits else "Damnthatsinteresting"
        clean_q = urllib.parse.quote(query.strip())
        
        for instance in REDLIB_INSTANCES:
            try:
                url = f"{instance}/r/{sub}/search.json?q={clean_q}&restrict_sr=1&sort=top&t=all&limit={n*2}"
                r = self.session.get(url, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    children = data.get("data", {}).get("children", [])
                    for child in children:
                        it = child.get("data", {})
                        if not it.get("is_video"):
                            continue
                        media = it.get("media") or {}
                        r_vid = media.get("reddit_video") if isinstance(media, dict) else None
                        f_url = r_vid.get("fallback_url") if r_vid else None
                        if f_url:
                            candidates.append({
                                "source": "Reddit",
                                "video_url": f_url,
                                "thumb_url": it.get("thumbnail") or f_url,
                                "title": it.get("title", ""),
                                "duration": float(r_vid.get("duration", 10.0)) if r_vid else 10.0,
                                "uploader_name": f"r/{it.get('subreddit', 'Reddit')}",
                                "uploader_handle": f"u/{it.get('author', 'RedditUser')} (r/{it.get('subreddit', 'Reddit')})",
                                "channel_url": f"https://reddit.com/r/{it.get('subreddit', 'Reddit')}",
                                "score": it.get("score", 0)
                            })
                    if candidates:
                        break
            except Exception:
                continue
        return candidates[:n]

    def probe_and_mux_vredd_it(self, video_url: str, out_path: str) -> bool:
        """
        Directly extracts and muxes 1080p/720p video and audio from v.redd.it stream.
        Zero intermediate re-encoding overhead.
        """
        vid_id_match = re.search(r'v\.redd\.it\/([a-zA-Z0-9_-]+)', video_url)
        if not vid_id_match:
            return False
            
        video_id = vid_id_match.group(1)
        resolutions = ["DASH_1080.mp4", "DASH_720.mp4", "DASH_480.mp4", "DASH_360.mp4"]
        audio_candidates = ["DASH_AUDIO_128.mp4", "DASH_audio.mp4", "DASH_AUDIO_64.mp4"]
        
        best_video = None
        best_audio = None
        
        for res in resolutions:
            u = f"https://v.redd.it/{video_id}/{res}"
            try:
                r = self.session.head(u, timeout=2.5, allow_redirects=True)
                if r.status_code == 200:
                    best_video = u
                    break
            except Exception:
                pass
                
        if not best_video:
            best_video = f"https://v.redd.it/{video_id}/HLSPlaylist.m3u8"
            
        for aud in audio_candidates:
            u = f"https://v.redd.it/{video_id}/{aud}"
            try:
                r = self.session.head(u, timeout=2.5, allow_redirects=True)
                if r.status_code == 200:
                    best_audio = u
                    break
            except Exception:
                pass
                
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        ua_hdr = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
"
        
        if best_video.endswith(".m3u8"):
            cmd = ["ffmpeg", "-y", "-headers", ua_hdr, "-i", best_video, "-c", "copy", "-movflags", "+faststart", out_path]
        elif best_audio:
            cmd = [
                "ffmpeg", "-y",
                "-headers", ua_hdr, "-i", best_video,
                "-headers", ua_hdr, "-i", best_audio,
                "-c:v", "copy", "-c:a", "aac",
                "-map", "0:v:0", "-map", "1:a:0?",
                "-movflags", "+faststart", out_path
            ]
        else:
            cmd = ["ffmpeg", "-y", "-headers", ua_hdr, "-i", best_video, "-c:v", "copy", "-movflags", "+faststart", out_path]
            
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=35)
            return res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 10_000
        except Exception:
            return False

    def get_reddit_candidates(self, query: str, niche: str = "general", n: int = 5) -> List[Dict]:
        """
        Unified Reddit candidate getter:
        1. Probes direct PullPush & Redlib video posts.
        2. Merges with semantically discovered authentic community footage search queries.
        """
        all_cands = []
        # 1. PullPush direct stream check
        pp_cands = self.search_pullpush_videos(query, niche=niche, n=n)
        all_cands.extend(pp_cands)
        
        # 2. Redlib mirror check
        if len(all_cands) < n:
            rl_cands = self.search_redlib_videos(query, niche=niche, n=n - len(all_cands))
            all_cands.extend(rl_cands)
        
        # 3. Semantic footage discovery queries
        if len(all_cands) < n:
            discovered = self.discover_community_footage(query, niche=niche, max_items=n - len(all_cands))
            for disc in discovered:
                sq = disc.get("search_query")
                if sq:
                    from pipeline.phase4_broll import _youtube_candidates
                    yt_results = _youtube_candidates(sq, n=2)
                    for yr in yt_results:
                        if disc.get("attribution_tag") and "r/" in disc.get("attribution_tag"):
                            yr["uploader_handle"] = disc.get("attribution_tag")
                        all_cands.append(yr)
                        if len(all_cands) >= n:
                            break
                            
        return all_cands[:n]


_engine_instance = None

def get_reddit_engine() -> RedditVideoEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RedditVideoEngine()
    return _engine_instance
