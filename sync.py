"""Pull the latest stats from Instagram into the local database.

Run it once a day (see README for scheduling):
    python sync.py          # real sync using IG_ACCESS_TOKEN from .env
    python sync.py --demo   # fill the database with fake data to preview the dashboard
"""
import argparse
import os
import random
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv

import db
from ig_client import InstagramClient, InstagramError

load_dotenv()
REFRESH_EVERY_DAYS = 7


def get_token(conn) -> str:
    # A refreshed token saved in the database wins over the one in .env.
    return db.get_setting(conn, "access_token") or os.getenv("IG_ACCESS_TOKEN", "")


def maybe_refresh(conn, client: InstagramClient, log=print):
    last = db.get_setting(conn, "token_refreshed_at")
    if last is None:
        # First run: start the clock; Instagram requires the token to be 24h old before refresh.
        db.set_setting(conn, "token_refreshed_at", datetime.now(timezone.utc).isoformat())
        return
    if datetime.now(timezone.utc) - datetime.fromisoformat(last) < timedelta(days=REFRESH_EVERY_DAYS):
        return
    try:
        new = client.refresh_token()
        db.set_setting(conn, "access_token", new)
        db.set_setting(conn, "token_refreshed_at", datetime.now(timezone.utc).isoformat())
        log("Access token refreshed for another 60 days.")
    except InstagramError as e:
        log(f"Token refresh skipped: {e}")


def run_sync(log=print, include_photos: bool = False) -> int:
    conn = db.connect()
    client = InstagramClient(get_token(conn))
    today = date.today().isoformat()

    me = client.me()
    db.upsert_account(conn, today, me)
    log(f"Connected as @{me.get('username')} ({me.get('followers_count')} followers)")

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
    maybe_refresh(conn, client, log)
    log("Sync complete.")
    return len(videos)


def seed_demo(days: int = 30, n_videos: int = 12):
    """Fake data so you can see the dashboard before connecting a real account."""
    conn = db.connect()
    rng = random.Random(7)
    start = date.today() - timedelta(days=days)
    topics = ["Long run day", "Race recap", "Track workout", "Morning routine", "Shoe review",
              "Tempo run", "Recovery tips", "Gym session", "Trail run", "Q&A", "Day in the life",
              "Pre-race nerves"]
    for v in range(n_videos):
        posted = start + timedelta(days=rng.randint(0, days - 3))
        mid = f"demo_{v}"
        db.upsert_media(conn, {
            "id": mid, "caption": topics[v % len(topics)], "media_type": "VIDEO",
            "media_product_type": "REELS", "timestamp": f"{posted}T15:00:00+0000",
            "permalink": "https://www.instagram.com/", "thumbnail_url": None,
        })
        if v in (2, 7):
            db.set_trial(conn, mid, True)
        ceiling = rng.choice([800, 2500, 6000, 20000])
        views = 0
        d = posted
        while d <= date.today():
            age = (d - posted).days + 1
            views = int(ceiling * (1 - 0.6 ** age) * rng.uniform(0.97, 1.03))
            likes = int(views * rng.uniform(0.04, 0.09))
            db.upsert_snapshot(conn, mid, d.isoformat(), {
                "views": views, "reach": int(views * 0.8), "likes": likes,
                "comments": int(likes * 0.08), "shares": int(likes * 0.12),
                "saved": int(likes * 0.1), "total_interactions": int(likes * 1.3),
                "ig_reels_avg_watch_time": rng.uniform(3500, 9000),
                "reels_skip_rate": rng.uniform(0.25, 0.6),
            })
            d += timedelta(days=1)
    for i in range(days + 1):
        d = start + timedelta(days=i)
        db.upsert_account(conn, d.isoformat(), {
            "username": "demo_account", "followers_count": 1200 + i * rng.randint(2, 9),
            "follows_count": 400, "media_count": 80 + i // 3,
        })
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
            raise SystemExit(f"Instagram error: {e}")
