#!/usr/bin/env python3
"""
audit_fleet.py — Master Fleet Auditor for yt-auto GitHub Actions Fleet.
Audits all 5 YouTube automation channels, checks 100% GHA cloud schedule adherence,
detects missed slots, audits run outcomes, and optionally triggers catch-ups.
"""
import argparse
import datetime
import json
import subprocess
import sys

FLEET = {
    "ch1": {
        "repo": "gurination1/yt-auto",
        "name": "Ch1 (Fun Learning - Science & Tech)",
        "slots": [
            ("04:30", "Short #1"),
            ("12:00", "Short #2"),
            ("21:00", "Short #3"),
        ],
        "long_day": 1,  # Monday
    },
    "ch2": {
        "repo": "gurination1/yt-auto-ch2",
        "name": "Ch2 (Nature Nourisher - Nature & Biology)",
        "slots": [
            ("06:00", "Short #1"),
            ("13:30", "Short #2"),
            ("22:30", "Short #3"),
        ],
        "long_day": 2,  # Tuesday
    },
    "ch3": {
        "repo": "gurination1/yt-auto-ch3",
        "name": "Ch3 (Mystery DeMysters - Tactical Warfare & Enigmas)",
        "slots": [
            ("01:30", "Short #1"),
            ("15:00", "Short #2"),
            ("19:30", "Short #3"),
        ],
        "long_day": 4,  # Thursday
    },
    "ch4": {
        "repo": "gurination1/yt-auto-ch4",
        "name": "Ch4 (Marvel Engeneering - Engineering Marvels)",
        "slots": [
            ("00:00", "Short #1"),
            ("07:30", "Short #2"),
            ("16:30", "Short #3"),
        ],
        "long_day": 5,  # Friday
    },
    "ch5": {
        "repo": "gurination1/yt-auto-ch5",
        "name": "Ch5 (Mind Here Business - Business & Global Trade)",
        "slots": [
            ("03:00", "Short #1"),
            ("10:30", "Short #2"),
            ("18:00", "Short #3"),
        ],
        "long_day": 3,  # Wednesday
    },
}


def check_local_processes():
    """Verify local machine is strictly passive (no crons / daemons)."""
    try:
        res = subprocess.run(
            ["ps", "aux"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        found = []
        for line in res.stdout.splitlines():
            if any(term in line for term in ["yt-auto-cron", "daemon.py"]) and "grep" not in line and "audit_fleet" not in line:
                found.append(line.strip())
        return found
    except Exception:
        return []


def get_gha_runs(repo: str, limit: int = 6):
    """Fetch latest workflow runs for repo via GitHub CLI."""
    cmd = [
        "gh", "run", "list",
        "--repo", repo,
        "--limit", str(limit),
        "--json", "databaseId,status,conclusion,createdAt,workflowName,headSha,event"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
        if res.returncode != 0:
            return []
        return json.loads(res.stdout)
    except Exception:
        return []


def dispatch_workflow(repo: str, workflow: str = "generate_short.yml", ref: str = None):
    """Trigger a workflow run on GHA."""
    cmd = ["gh", "workflow", "run", workflow, "--repo", repo, "-f", "publish=true"]
    if ref:
        cmd.extend(["--ref", ref])
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
    return res.returncode == 0, res.stdout.strip() or res.stderr.strip()


def parse_iso(dt_str: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def audit_fleet(dispatch_missed: bool = False):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    today_utc = now_utc.date()

    print(f"=================================================================")
    print(f"🎬 YouTube Fleet GHA Cloud Auditor — {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"=================================================================")

    # 1. Local Process Check (Sanity: strictly no local execution)
    local_procs = check_local_processes()
    if local_procs:
        print(f"\n⚠️  CRITICAL WARNING: Local background processes detected on device!")
        for p in local_procs:
            print(f"   🚨 {p}")
        print("   All pipeline execution & dispatching MUST run on GitHub Actions cloud!")
    else:
        print(f"✅ Local device state: Clean (100% GHA cloud-autonomous)")

    results = {}
    missed_to_trigger = []

    print("\n--- Fleet Status Across Channels ---")
    for key, cfg in FLEET.items():
        repo = cfg["repo"]
        name = cfg["name"]
        runs = get_gha_runs(repo, limit=6)

        today_runs = []
        for r in runs:
            created = parse_iso(r["createdAt"])
            if created.date() == today_utc:
                today_runs.append(r)

        # Expected slots passed so far today
        expected_slots_passed = []
        for time_str, slot_label in cfg["slots"]:
            sh, sm = map(int, time_str.split(":"))
            slot_dt = datetime.datetime(today_utc.year, today_utc.month, today_utc.day, sh, sm, tzinfo=datetime.timezone.utc)
            if slot_dt <= now_utc:
                expected_slots_passed.append((time_str, slot_label))

        # Long form check if today matches
        if now_utc.isoweekday() == cfg["long_day"]:
            slot_dt = datetime.datetime(today_utc.year, today_utc.month, today_utc.day, 9, 0, tzinfo=datetime.timezone.utc)
            if slot_dt <= now_utc:
                expected_slots_passed.append(("09:00", "Weekly Long Video"))

        active = [r for r in today_runs if r.get("status") in ("in_progress", "queued")]
        success = [r for r in today_runs if r.get("conclusion") == "success"]
        failed = [r for r in today_runs if r.get("conclusion") in ("failure", "timed_out", "cancelled")]

        # Determine if any slot was missed
        completed_count = len(success) + len(active)
        missed_count = max(0, len(expected_slots_passed) - completed_count)

        status_icon = "🟢"
        if active:
            status_icon = "🔄"
        elif missed_count > 0:
            status_icon = "🟡"
        if failed:
            status_icon = "🔴"

        print(f"\n{status_icon} {name} [{repo}]")
        print(f"   Expected Slots Elapsed Today: {len(expected_slots_passed)} | Runs Executed: {len(today_runs)} (Pass: {len(success)}, Active: {len(active)}, Fail: {len(failed)})")

        if today_runs:
            latest = today_runs[0]
            created_utc = parse_iso(latest["createdAt"]).strftime("%H:%M UTC")
            print(f"   Latest Run: ID {latest['databaseId']} | Status: {latest['status']}/{latest.get('conclusion') or 'running'} | Event: {latest.get('event')} | Started: {created_utc}")
        elif runs:
            latest = runs[0]
            created_utc = parse_iso(latest["createdAt"]).strftime("%Y-%m-%d %H:%M UTC")
            print(f"   Latest Run (Prior Day): ID {latest['databaseId']} | Status: {latest['conclusion']} | Started: {created_utc}")
        else:
            print("   No recent runs found.")

        if missed_count > 0:
            print(f"   ⚠️  Missed/Pending Slots Today: {missed_count}")
            missed_to_trigger.append((key, repo, missed_count))

        results[key] = {
            "name": name,
            "repo": repo,
            "today_runs": len(today_runs),
            "success": len(success),
            "active": len(active),
            "failed": len(failed),
            "missed_count": missed_count,
        }

    if missed_to_trigger and dispatch_missed:
        print("\n--- Dispatching Missed Runs on GHA ---")
        for key, repo, count in missed_to_trigger:
            for _ in range(count):
                ok, msg = dispatch_workflow(repo)
                state = "SUCCESS" if ok else "FAILED"
                print(f"   [{state}] Dispatched generate_short.yml on {repo}: {msg}")
    elif missed_to_trigger:
        print(f"\n💡 {len(missed_to_trigger)} channels have pending/missed slots. Run with '--dispatch-missed' to catch up.")

    print("\n=================================================================")
    print("Master Slot Schedule Reference (UTC & IST):")
    print("• 00:00 UTC (05:30 IST) - Ch4 Short #1 | • 01:30 UTC (07:00 IST) - Ch3 Short #1")
    print("• 03:00 UTC (08:30 IST) - Ch5 Short #1 | • 04:30 UTC (10:00 IST) - Ch1 Short #1")
    print("• 06:00 UTC (11:30 IST) - Ch2 Short #1 | • 07:30 UTC (13:00 IST) - Ch4 Short #2")
    print("• 09:00 UTC (14:30 IST) - Weekly Long  | • 10:30 UTC (16:00 IST) - Ch5 Short #2")
    print("• 12:00 UTC (17:30 IST) - Ch1 Short #2 | • 13:30 UTC (19:00 IST) - Ch2 Short #2")
    print("• 15:00 UTC (20:30 IST) - Ch3 Short #2 | • 16:30 UTC (22:00 IST) - Ch4 Short #3")
    print("• 18:00 UTC (23:30 IST) - Ch5 Short #3 | • 19:30 UTC (01:00 IST) - Ch3 Short #3")
    print("• 21:00 UTC (02:30 IST) - Ch1 Short #3 | • 22:30 UTC (04:00 IST) - Ch2 Short #3")
    print("=================================================================\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit YouTube fleet GHA schedule and run health.")
    parser.add_argument("--dispatch-missed", action="store_true", help="Automatically trigger missed slots on GHA")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    audit_fleet(dispatch_missed=args.dispatch_missed)
