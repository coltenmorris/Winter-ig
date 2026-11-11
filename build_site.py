"""Build the static website in docs/ (served by GitHub Pages) from ig_analytics.db.

    python build_site.py

Copies the page templates from site/ and writes docs/data.js with your latest stats.
"""
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import db
import flags as flags_mod

ROOT = Path(__file__).parent
SRC, OUT = ROOT / "site", ROOT / "docs"
TZ = ZoneInfo("America/Los_Angeles")  # Pacific time throughout
METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
           "avg_watch_ms", "skip_rate"]


def num(v):
    return None if v is None else (round(v, 4) if isinstance(v, float) else v)


def stats(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = {k: num(row[k]) for k in METRICS}
    # Instagram returns 0 for metrics it doesn't supply; treat impossible zeros as missing.
    if d["views"]:
        for k in ("reach", "avg_watch_ms", "skip_rate"):
            if not d[k]:
                d[k] = None
        if d["reach"] is None and not d["saved"] and d["likes"]:
            d["saved"] = None
    parts = [d[k] for k in ("likes", "comments", "shares", "saved") if d[k] is not None]
    inter = max(d["total_interactions"] or 0, sum(parts)) if (parts or d["total_interactions"]) else None
    d["interactions"] = inter
    d["engagement"] = round(inter / d["views"], 4) if inter is not None and d["views"] else None
    d["watch_s"] = round(d["avg_watch_ms"] / 1000, 1) if d["avg_watch_ms"] else None
    d["date"] = row["captured_date"]
    return d


def build():
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    setting = lambda k: (conn.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone() or [None])[0]

    fl = flags_mod.load_flags()
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
            "posted": posted.strftime("%Y-%m-%dT%H:%M"), "ts": int(posted.timestamp() * 1000), "date": posted.strftime("%Y-%m-%d"),
            "thumb": m["thumbnail_url"], "link": m["permalink"], "trial": bool(m["is_trial"]) or m["id"] in fl["trial"],
            "ad": m["id"] in fl["ads"], "brand": fl["ads"].get(m["id"], {}).get("brand", ""),
            "kind": db.media_kind(m["media_type"], m["product_type"]), "media_type": m["media_type"],
            "h24": at(1, 1), "week": at(7, 2), "total": stats(snaps[-1]),
            "series": [[age, s["views"] if s["views"] is not None else s["likes"]] for age, s in aged],
        })

    stories = []
    for s in conn.execute("""SELECT s.*, st.* FROM stories s LEFT JOIN story_stats st ON st.story_id = s.id
                             ORDER BY s.posted_at DESC"""):
        posted = datetime.fromisoformat(s["posted_at"].replace("+0000", "+00:00")).astimezone(TZ)
        stories.append({"id": s["id"], "posted": posted.strftime("%Y-%m-%dT%H:%M"), "ts": int(posted.timestamp() * 1000),
                        "date": posted.strftime("%Y-%m-%d"), "type": s["media_type"], "thumb": s["thumbnail_url"],
                        "link": s["permalink"], **{c: s[c] for c in db.STORY_COLS}})

    followers = [{"date": r["captured_date"], "n": r["followers"]}
                 for r in conn.execute("SELECT captured_date, followers FROM account_snapshots ORDER BY captured_date")]
    daily = [{"date": r["captured_date"], "views": r["views"], "reach": r["reach"]}
             for r in conn.execute("SELECT * FROM account_daily ORDER BY captured_date")]
    all_demo = {}
    for r in conn.execute("SELECT breakdown, label, value FROM demographics"):
        all_demo.setdefault(r["breakdown"], {})[r["label"]] = r["value"]
    # Viewers (accounts reached this month) and followers, each with last month's breakdown.
    # Viewers "all time": Instagram only reports a month at a time, so add up every saved month.
    viewers_all, months_seen = {}, set()
    for r in conn.execute("SELECT month, breakdown, label, value FROM demographics_monthly WHERE audience='viewers'"):
        months_seen.add(r["month"])
        viewers_all.setdefault(r["breakdown"], {})
        viewers_all[r["breakdown"]][r["label"]] = viewers_all[r["breakdown"]].get(r["label"], 0) + r["value"]
    viewers_since = (datetime.strptime(min(months_seen) + "-01", "%Y-%m-%d").strftime("%B %Y")
                     if months_seen else None)
    audiences = {
        "followers": {k: v for k, v in all_demo.items() if ":" not in k},
        "viewers": viewers_all,
    }
    audiences = {k: v for k, v in audiences.items() if v}
    demo_source = "followers" if "followers" in audiences else "viewers"
    demo = audiences.get(demo_source, {})
    today_d = datetime.now(TZ).date()
    prev_month = (today_d.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    audiences_prev = {}
    for r in conn.execute("SELECT audience, breakdown, label, value FROM demographics_monthly WHERE month=?", (prev_month,)):
        audiences_prev.setdefault(r["audience"], {}).setdefault(r["breakdown"], {})[r["label"]] = r["value"]
    demo_prev = audiences_prev.get(demo_source, {})
    prev_month_name = datetime.strptime(prev_month + "-01", "%Y-%m-%d").strftime("%B")

    data = {
        "profile": {"name": setting("profile_name"), "username": setting("profile_username"),
                    "bio": setting("profile_biography"), "pic": setting("profile_profile_picture_url")},
        "followers": followers, "daily": daily, "demographics": demo, "demo_source": demo_source,
        "demo_prev": demo_prev, "demo_prev_month": prev_month_name,
        "audiences": audiences, "audiences_prev": {"followers": audiences_prev.get("followers", {})},
        "viewers_since": viewers_since,
        "stories": stories, "views_30d": float(setting("views_30d")) if setting("views_30d") not in (None, "", "None") else None, "reels": reels,
        "created": os.getenv("ACCOUNT_CREATED") or "June 15th, 2026",
        "contact": os.getenv("CONTACT_EMAIL") or None, "tagline": os.getenv("CREATOR_TAGLINE") or None,
        "updated": datetime.now(timezone.utc).astimezone(TZ).strftime("%B %-d, %Y"),
    }
    conn.close()

    OUT.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    for f in SRC.iterdir():
        if f.is_file():
            if f.suffix == ".html":
                # Version the asset links so browsers fetch fresh data after each sync.
                text = f.read_text()
                for asset in ("data.js", "common.js", "style.css", "thermal.css"):
                    text = text.replace(f'"{asset}"', f'"{asset}?v={stamp}"')
                (OUT / f.name).write_text(text)
            else:
                shutil.copy2(f, OUT / f.name)
    (OUT / ".nojekyll").touch()
    (OUT / "data.js").write_text("window.DATA = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"Built site with {len(reels)} reels into {OUT}")


if __name__ == "__main__":
    build()
