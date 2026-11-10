"""Pull the latest stats from Instagram into the local database.

Run it once a day (see README for scheduling):
    python sync.py          # real sync using IG_ACCESS_TOKEN from .env
    python sync.py --demo   # fill the database with fake data to preview the dashboard
"""
import argparse
import os
import random
import subprocess
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv

import db
from ig_client import InstagramClient, InstagramError

load_dotenv()
REFRESH_EVERY_DAYS = 7


TOKEN_FILE = Path(__file__).with_name(".token")  # gitignored; never stored in the database


def clean_token(raw: str) -> str:
    """Forgive common paste mistakes: spaces, line breaks, quotes, or a 'NAME=' prefix."""
    tok = "".join(raw.split())
    for prefix in ("IG_ACCESS_TOKEN=", "access_token=", "Bearer"):
        if tok.startswith(prefix):
            tok = tok[len(prefix):]
    return tok.strip("\"'")


def describe_token(tok: str) -> str:
    """Safe hint for debugging: never prints the token itself."""
    if not tok:
        return "No token found. Check the secret is named exactly IG_ACCESS_TOKEN."
    hint = f"Token is {len(tok)} characters and starts with '{tok[:3]}'."
    if len(tok) < 60:
        hint += " That's shorter than expected; part of it may be missing."
    return hint


def get_token(conn=None) -> str:
    # A refreshed token saved locally wins over the one in .env / GitHub secret.
    if TOKEN_FILE.exists():
        return clean_token(TOKEN_FILE.read_text())
    return clean_token(os.getenv("IG_ACCESS_TOKEN", ""))


def save_token(new: str, log=print):
    """Store a refreshed token. In GitHub Actions, update the repo secret if GH_PAT is set."""
    if os.getenv("GITHUB_ACTIONS"):
        if os.getenv("GH_PAT"):
            r = subprocess.run(
                ["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
                input=new, text=True, capture_output=True, env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]},
            )
            log("Token refreshed and IG_ACCESS_TOKEN secret updated." if r.returncode == 0 else f"Could not update secret: {r.stderr.strip()}")
        else:
            log("Token refreshed but not saved (no GH_PAT secret). Replace IG_ACCESS_TOKEN within 60 days.")
    else:
        TOKEN_FILE.write_text(new)
        log("Access token refreshed for another 60 days.")


def maybe_refresh(conn, client: InstagramClient, log=print):
    last = db.get_setting(conn, "token_refreshed_at")
    if last is None:
        # First run: start the clock; Instagram requires the token to be 24h old before refresh.
        db.set_setting(conn, "token_refreshed_at", datetime.now(timezone.utc).isoformat())
        return
    if datetime.now(timezone.utc) - datetime.fromisoformat(last) < timedelta(days=REFRESH_EVERY_DAYS):
        return
    try:
        save_token(client.refresh_token(), log)
        db.set_setting(conn, "token_refreshed_at", datetime.now(timezone.utc).isoformat())
    except InstagramError as e:
        log(f"Token refresh skipped: {e}")


def run_sync(log=print, include_photos: bool = False) -> int:
    conn = db.connect()
    client = InstagramClient(get_token(conn))
    today = date.today().isoformat()

    me = client.me()
    db.upsert_account(conn, today, me)
    db.save_profile(conn, me)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.upsert_account_daily(conn, yesterday, client.account_daily())
    db.replace_demographics(conn, today, client.demographics())
    log(f"Connected as @{me.get('username')} ({me.get('followers_count')} followers) via {me.get('api')}")

    media = client.list_media()
    videos = [m for m in media if include_photos or m.get("media_type") == "VIDEO"]
    log(f"Found {len(media)} posts, {len(videos)} videos. Pulling insights...")

    for i, m in enumerate(videos, 1):
        db.upsert_media(conn, m)
        is_reel = m.get("media_product_type", "REELS") == "REELS"
        ins = client.media_insights(m["id"], is_reel)
        # Fallback to the basic counts if insights were empty (e.g. very new post).
        ins.setdefault("likes", m.get("like_count"))
        ins.setdefault("comments", m.get("comments_count"))
        db.upsert_snapshot(conn, m["id"], today, ins)
        if i % 10 == 0:
            log(f"  {i}/{len(videos)}")
    conn.commit()
    if videos and client.insight_errors and len(client.insight_errors) >= len(videos):
        log("WARNING: Instagram returned no views/reach/watch-time insights. Only likes and comments were saved.")
        log("  First error: " + client.insight_errors[0])
        rep = client.permission_report()
        if rep:
            log("  " + rep)
        log("  Fix: generate a new token with the instagram_manage_insights permission and update IG_ACCESS_TOKEN.")
    maybe_refresh(conn, client, log)
    log("Sync complete.")
    return len(videos)


def seed_demo(days: int = 75, n_videos: int = 28):
    """Fake data so you can see the dashboard before connecting a real account."""
    conn = db.connect()
    rng = random.Random(7)
    start = date.today() - timedelta(days=days)
    ideas = [
        ("Sub-5 mile attempt #running #mile", 2.2), ("What I eat before a race #runnerfood", 1.4),
        ("Track workout breakdown #trackworkout #running", 1.6), ("Shoe review: daily trainers #runningshoes", 1.1),
        ("Morning long run vlog #longrun", 0.9), ("D1 cross country memories #xc #ncaa", 1.8),
        ("Recovery routine #recovery", 0.8), ("Race day POV #raceday #running", 2.5),
        ("Easy run pace explained #runningtips", 1.3), ("Gym session for runners #strength", 0.9),
        ("Trail run sunrise #trailrunning", 1.0), ("Q&A: how I got faster #runningtips", 1.5),
    ]
    for v in range(n_videos):
        posted = start + timedelta(days=int(v * (days - 3) / n_videos) + rng.randint(0, 2))
        hour = rng.choice([7, 8, 12, 17, 18, 19, 20, 21])
        cap, boost = ideas[v % len(ideas)]
        mid = f"demo_{v}"
        db.upsert_media(conn, {
            "id": mid, "caption": cap, "media_type": "VIDEO", "media_product_type": "REELS",
            "timestamp": (datetime(posted.year, posted.month, posted.day, hour) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S+0000"),
            "permalink": "https://www.instagram.com/", "thumbnail_url": None,
        })
        if v % 6 == 4:
            db.set_trial(conn, mid, True)
        ceiling = rng.uniform(1500, 9000) * boost * (1.4 if hour >= 17 else 1.0) * (1 + v / n_videos)
        d = posted
        while d <= date.today():
            age = (d - posted).days + 1
            views = int(ceiling * (1 - 0.55 ** age))
            likes = int(views * rng.uniform(0.05, 0.1))
            db.upsert_snapshot(conn, mid, d.isoformat(), {
                "views": views, "reach": int(views * 0.78), "likes": likes,
                "comments": int(likes * 0.07), "shares": int(likes * 0.15),
                "saved": int(likes * 0.12), "total_interactions": int(likes * 1.35),
                "ig_reels_avg_watch_time": rng.uniform(4000, 11000),
                "reels_skip_rate": rng.uniform(0.22, 0.55),
            })
            d += timedelta(days=1)
    followers = 2400
    for i in range(days + 1):
        d = start + timedelta(days=i)
        followers += rng.randint(3, 22)
        db.upsert_account(conn, d.isoformat(), {
            "username": "colten.runs", "followers_count": followers,
            "follows_count": 410, "media_count": 120 + i // 3,
        })
        db.upsert_account_daily(conn, d.isoformat(), {
            "reach": rng.randint(2500, 9000), "views": rng.randint(5000, 16000),
            "accounts_engaged": rng.randint(300, 900), "total_interactions": rng.randint(500, 1500),
        })
    db.replace_demographics(conn, date.today().isoformat(), {
        "age": {"13-17": 120, "18-24": 1210, "25-34": 980, "35-44": 410, "45-54": 160, "55-64": 60, "65+": 20},
        "gender": {"M": 1690, "F": 1210, "U": 60},
        "country": {"US": 2150, "CA": 180, "GB": 140, "AU": 95, "KE": 60, "MX": 45},
        "city": {"Minneapolis, Minnesota": 420, "Miami, Florida": 310, "Pittsburgh, Pennsylvania": 280,
                 "New York, New York": 190, "Chicago, Illinois": 150, "Los Angeles, California": 120},
    })
    db.save_profile(conn, {"username": "colten.runs", "name": "Colten Morris",
                           "biography": "D1 runner sharing training, racing and recovery."})
    conn.commit()
    print(f"Demo data written to {db.DB_PATH}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="fill the database with fake data")
    p.add_argument("--include-photos", action="store_true", help="also track photo posts")
    a = p.parse_args()
    if a.demo:
        seed_demo()
    else:
        try:
            run_sync(include_photos=a.include_photos)
        except InstagramError as e:
            msg = f"Instagram error: {e}"
            if "token" in str(e).lower() or "oauth" in str(e).lower():
                msg += "\n" + describe_token(get_token())
            raise SystemExit(msg)
