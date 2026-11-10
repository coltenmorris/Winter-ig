"""Build the static website in docs/ (served by GitHub Pages) from ig_analytics.db.

    python build_site.py

Copies the page templates from site/ and writes docs/data.js with your latest stats.
"""
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import db

ROOT = Path(__file__).parent
SRC, OUT = ROOT / "site", ROOT / "docs"
TZ = ZoneInfo("America/New_York")
METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
           "avg_watch_ms", "skip_rate"]


def num(v):
    return None if v is None else (round(v, 4) if isinstance(v, float) else v)


def stats(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = {k: num(row[k]) for k in METRICS}
    inter = d["total_interactions"]
    if inter is None:
        parts = [d[k] for k in ("likes", "comments", "shares", "saved") if d[k] is not None]
        inter = sum(parts) if parts else None
    d["interactions"] = inter
    d["engagement"] = round(inter / d["views"], 4) if inter is not None and d["views"] else None
    d["watch_s"] = round(d["avg_watch_ms"] / 1000, 1) if d["avg_watch_ms"] else None
    d["date"] = row["captured_date"]
    return d


def build():
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    setting = lambda k: (conn.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone() or [None])[0]

    reels = []
    for m in conn.execute("SELECT * FROM media ORDER BY posted_at DESC"):
        posted = datetime.fromisoformat(m["posted_at"].replace("+0000", "+00:00")).astimezone(TZ)
        snaps = conn.execute("SELECT * FROM media_snapshots WHERE media_id=? ORDER BY captured_date",
                             (m["id"],)).fetchall()
        if not snaps:
            continue
        aged = [((datetime.fromisoformat(s["captured_date"]).date() - posted.date()).days, s) for s in snaps]

        def at(day, slack):
            for age, s in aged:
                if age >= day:
                    return stats(s) if age <= day + slack else None
            return None

        caption = m["caption"] or ""
        reels.append({
            "id": m["id"], "caption": caption,
            "title": " ".join(w for w in caption.split("\n")[0].split() if not w.startswith("#"))[:70] or "Untitled",
            "tags": sorted({w[1:].lower().strip(".,!?") for w in caption.split() if w.startswith("#") and len(w) > 1}),
            "posted": posted.strftime("%Y-%m-%dT%H:%M"), "date": posted.strftime("%Y-%m-%d"),
            "thumb": m["thumbnail_url"], "link": m["permalink"], "trial": bool(m["is_trial"]),
            "h24": at(1, 1), "week": at(7, 2), "total": stats(snaps[-1]),
            "series": [[age, s["views"] if s["views"] is not None else s["likes"]] for age, s in aged],
        })

    followers = [{"date": r["captured_date"], "n": r["followers"]}
                 for r in conn.execute("SELECT captured_date, followers FROM account_snapshots ORDER BY captured_date")]
    daily = [{"date": r["captured_date"], "views": r["views"], "reach": r["reach"]}
             for r in conn.execute("SELECT * FROM account_daily ORDER BY captured_date")]
    demo = {}
    for r in conn.execute("SELECT breakdown, label, value FROM demographics"):
        demo.setdefault(r["breakdown"], {})[r["label"]] = r["value"]

    data = {
        "profile": {"name": setting("profile_name"), "username": setting("profile_username"),
                    "bio": setting("profile_biography"), "pic": setting("profile_profile_picture_url")},
        "followers": followers, "daily": daily, "demographics": demo, "reels": reels,
        "contact": os.getenv("CONTACT_EMAIL") or None, "tagline": os.getenv("CREATOR_TAGLINE") or None,
        "updated": datetime.now(timezone.utc).astimezone(TZ).strftime("%B %-d, %Y"),
    }
    conn.close()

    OUT.mkdir(exist_ok=True)
    for f in SRC.iterdir():
        if f.is_file():
            shutil.copy2(f, OUT / f.name)
    (OUT / ".nojekyll").touch()
    (OUT / "data.js").write_text("window.DATA = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"Built site with {len(reels)} reels into {OUT}")


if __name__ == "__main__":
    build()
