"""Ask Instagram for each metric one at a time and print exactly what comes back.

    python diagnose.py

Never prints the access token.
"""
import json
import os

from dotenv import load_dotenv

from ig_client import InstagramClient, InstagramError
from sync import get_token

load_dotenv()


def show(label, fn):
    try:
        out = json.dumps(fn())
        print(f"OK   {label}: {out[:400]}")
    except InstagramError as e:
        print(f"FAIL {label}: {e}")


c = InstagramClient(get_token())
host = c.connect()
print("API host:", host, "| account id set:", c.uid != "me")
show("permissions", lambda: c._get("me/permissions", host="https://graph.facebook.com").get("data"))
media = c.list_media(limit=3)
m = max(media, key=lambda x: x.get("timestamp", ""))
print("Newest media:", m.get("media_type"), m.get("media_product_type"), m.get("timestamp"))

for metric in ["views", "reach", "saved", "shares", "likes", "comments", "total_interactions",
               "ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "reels_skip_rate", "reposts"]:
    show(f"media {metric}", lambda: c._get(f"{m['id']}/insights", {"metric": metric}))
show("media all-at-once", lambda: c._get(f"{m['id']}/insights",
                                          {"metric": "views,reach,saved,shares,total_interactions"}))

for metric, extra in [("reach", {"period": "day", "metric_type": "total_value"}),
                      ("views", {"period": "day", "metric_type": "total_value"}),
                      ("accounts_engaged", {"period": "day", "metric_type": "total_value"}),
                      ("follower_count", {"period": "day"})]:
    show(f"account {metric}", lambda: c._get(f"{c.uid}/insights", {"metric": metric, **extra}))

for metric in ["follower_demographics", "engaged_audience_demographics", "reached_audience_demographics"]:
    for b in ["gender", "country", "city", "age"]:
        params = {"metric": metric, "period": "lifetime", "metric_type": "total_value", "breakdown": b}
        if metric != "follower_demographics":
            params["timeframe"] = "this_month"
        show(f"{metric} {b}", lambda: c._get(f"{c.uid}/insights", params))
        if metric == "follower_demographics" and b == "gender":
            show("follower_demographics gender (with timeframe)", lambda: c._get(
                f"{c.uid}/insights", {**params, "timeframe": "this_month"}))
