#!/usr/bin/env python3
"""
GitHub Actions Fallback Deduplication Guard
Checks if the current scheduled slot was already generated & published by the primary server.
Exits with code 0 and sets SHOULD_RUN=false if already uploaded, or SHOULD_RUN=true if fallback is needed.
"""
import os
import sys
import json
import datetime
import urllib.request
import re

def check_fallback():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    
    # 1. Check local / git published_slots.json
    slots_file = "published_slots.json"
    if os.path.exists(slots_file):
        try:
            with open(slots_file, "r") as f:
                slots_data = json.load(f)
            # Find any publication for this repo in the last 2 hours
            for slot_id, info in slots_data.items():
                pub_at_str = info.get("published_at")
                if pub_at_str:
                    pub_dt = datetime.datetime.fromisoformat(pub_at_str.replace("Z", "+00:00"))
                    diff_hours = (now_utc - pub_dt).total_seconds() / 3600.0
                    if diff_hours < 2.0:
                        print(f"✅ [Fallback Check] Found recent upload for this channel: {info.get('title')} (Slot ID: {slot_id}, {diff_hours:.1f}h ago).")
                        print(f"Primary server has already published. Skipping GitHub Actions fallback.")
                        set_github_output("should_run", "false")
                        return
        except Exception as e:
            print(f"Warning reading published_slots.json: {e}")

    # 2. Check published_topics.json for recent timestamps
    topics_file = "published_topics.json"
    if os.path.exists(topics_file):
        try:
            with open(topics_file, "r") as f:
                topics_data = json.load(f)
            for item in topics_data:
                if isinstance(item, dict):
                    pub_at_str = item.get("published_at") or item.get("created_at")
                    if pub_at_str:
                        pub_dt = datetime.datetime.fromisoformat(pub_at_str.replace("Z", "+00:00"))
                        diff_hours = (now_utc - pub_dt).total_seconds() / 3600.0
                        if diff_hours < 2.0:
                            print(f"✅ [Fallback Check] Recent topic published {diff_hours:.1f}h ago: {item.get('title')}. Skipping fallback.")
                            set_github_output("should_run", "false")
                            return
        except Exception as e:
            print(f"Warning reading published_topics.json: {e}")

    print("⚠️ [Fallback Check] No recent video detected from primary server in the current slot window.")
    print("🚀 Triggering GitHub Actions automated fallback generation & upload!")
    set_github_output("should_run", "true")

def set_github_output(name: str, value: str):
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out and os.path.exists(gh_out):
        with open(gh_out, "a") as f:
            f.write(f"{name}={value}
")
    print(f"OUTPUT: {name}={value}")

if __name__ == "__main__":
    check_fallback()
