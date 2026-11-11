"""SQLite storage: one row per video, plus a daily snapshot of each video's stats."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("ig_analytics.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    id TEXT PRIMARY KEY,
    caption TEXT,
    media_type TEXT,
    product_type TEXT,
    posted_at TEXT,
    permalink TEXT,
    thumbnail_url TEXT,
    is_trial INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS media_snapshots (
    media_id TEXT,
    captured_date TEXT,
    views INTEGER, reach INTEGER, likes INTEGER, comments INTEGER,
    shares INTEGER, saved INTEGER, total_interactions INTEGER, reposts INTEGER,
    avg_watch_ms REAL, total_watch_ms REAL, skip_rate REAL,
    PRIMARY KEY (media_id, captured_date)
);
CREATE TABLE IF NOT EXISTS account_snapshots (
    captured_date TEXT PRIMARY KEY,
    username TEXT, followers INTEGER, following INTEGER, media_count INTEGER
);
CREATE TABLE IF NOT EXISTS account_daily (
    captured_date TEXT PRIMARY KEY,
    reach INTEGER, views INTEGER, accounts_engaged INTEGER, total_interactions INTEGER
);
CREATE TABLE IF NOT EXISTS demographics (
    breakdown TEXT, label TEXT, value INTEGER, captured_date TEXT,
    PRIMARY KEY (breakdown, label)
);
CREATE TABLE IF NOT EXISTS demographics_monthly (
    month TEXT, audience TEXT, breakdown TEXT, label TEXT, value INTEGER,
    PRIMARY KEY (month, audience, breakdown, label)
);
CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY, media_type TEXT, posted_at TEXT, permalink TEXT, thumbnail_url TEXT, caption TEXT
);
CREATE TABLE IF NOT EXISTS story_stats (
    story_id TEXT PRIMARY KEY, captured_at TEXT,
    views INTEGER, reach INTEGER, replies INTEGER, shares INTEGER, total_interactions INTEGER,
    follows INTEGER, profile_visits INTEGER, navigation INTEGER,
    taps_forward INTEGER, taps_back INTEGER, exits INTEGER, swipe_forward INTEGER
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()


def upsert_media(conn, m: dict):
    # Keep the user's manual trial-reel flag when updating.
    conn.execute(
        """INSERT INTO media(id, caption, media_type, product_type, posted_at, permalink, thumbnail_url)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET caption=excluded.caption, media_type=excluded.media_type,
             product_type=excluded.product_type, permalink=excluded.permalink,
             thumbnail_url=excluded.thumbnail_url""",
        (m["id"], m.get("caption"), m.get("media_type"), m.get("media_product_type"),
         m.get("timestamp"), m.get("permalink"),
         m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") != "VIDEO" else None)),
    )


def upsert_snapshot(conn, media_id: str, date: str, ins: dict):
    conn.execute(
        """INSERT OR REPLACE INTO media_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (media_id, date, ins.get("views"), ins.get("reach"), ins.get("likes"),
         ins.get("comments"), ins.get("shares"), ins.get("saved"),
         ins.get("total_interactions"), ins.get("reposts"),
         ins.get("ig_reels_avg_watch_time"), ins.get("ig_reels_video_view_total_time"),
         ins.get("reels_skip_rate")),
    )


def upsert_account(conn, date: str, me: dict):
    conn.execute(
        "INSERT OR REPLACE INTO account_snapshots VALUES (?,?,?,?,?)",
        (date, me.get("username"), me.get("followers_count"), me.get("follows_count"),
         me.get("media_count")),
    )


def set_trial(conn, media_id: str, is_trial: bool):
    conn.execute("UPDATE media SET is_trial=? WHERE id=?", (1 if is_trial else 0, media_id))
    conn.commit()


def upsert_account_daily(conn, date: str, d: dict):
    if not d:
        return
    conn.execute(
        "INSERT OR REPLACE INTO account_daily VALUES (?,?,?,?,?)",
        (date, d.get("reach"), d.get("views"), d.get("accounts_engaged"), d.get("total_interactions")),
    )


def replace_demographics(conn, date: str, demo: dict):
    for breakdown, rows in demo.items():
        if not rows:
            continue
        conn.execute("DELETE FROM demographics WHERE breakdown=?", (breakdown,))
        conn.executemany(
            "INSERT INTO demographics VALUES (?,?,?,?)",
            [(breakdown, k, int(v), date) for k, v in rows.items()],
        )


def save_profile(conn, me: dict):
    for k in ("username", "name", "biography", "profile_picture_url"):
        if me.get(k):
            set_setting(conn, f"profile_{k}", me[k])


def media_kind(media_type, product_type) -> str:
    """'reel' for reels and videos, 'post' for photos and carousels."""
    return "reel" if product_type == "REELS" or media_type == "VIDEO" else "post"


def save_monthly_demographics(conn, month: str, audience: str, demo: dict):
    """Keep one audience breakdown per calendar month (the latest sync in that month wins)."""
    for breakdown, rows in demo.items():
        if not rows:
            continue
        conn.execute("DELETE FROM demographics_monthly WHERE month=? AND audience=? AND breakdown=?",
                     (month, audience, breakdown))
        conn.executemany("INSERT INTO demographics_monthly VALUES (?,?,?,?,?)",
                         [(month, audience, breakdown, k, int(v)) for k, v in rows.items()])


STORY_COLS = ["views", "reach", "replies", "shares", "total_interactions", "follows", "profile_visits",
              "navigation", "taps_forward", "taps_back", "exits", "swipe_forward"]


def upsert_story(conn, s: dict, captured_at: str, ins: dict):
    """Stories keep one row of stats: the latest capture before they expire. A failed capture never wipes a good one."""
    thumb = s.get("thumbnail_url") or (s.get("media_url") if s.get("media_type") == "IMAGE" else None)
    conn.execute("""INSERT INTO stories(id, media_type, posted_at, permalink, thumbnail_url, caption) VALUES (?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET thumbnail_url=COALESCE(excluded.thumbnail_url, stories.thumbnail_url),
                    permalink=COALESCE(excluded.permalink, stories.permalink)""",
                 (s["id"], s.get("media_type"), s.get("timestamp"), s.get("permalink"), thumb, s.get("caption")))
    vals = [ins.get(c) for c in STORY_COLS]
    if all(v is None for v in vals):
        return
    sets = ", ".join(f"{c}=COALESCE(excluded.{c}, story_stats.{c})" for c in STORY_COLS)
    conn.execute(f"""INSERT INTO story_stats(story_id, captured_at, {", ".join(STORY_COLS)})
                     VALUES (?, ?, {", ".join("?" * len(STORY_COLS))})
                     ON CONFLICT(story_id) DO UPDATE SET captured_at=excluded.captured_at, {sets}""",
                 [s["id"], captured_at, *vals])
