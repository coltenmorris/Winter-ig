"""Check whether Instagram returns any audience demographics for a single reel or post."""
import json
from ig_client import InstagramClient, InstagramError
from sync import get_token

c = InstagramClient(get_token()); c.connect()
media = c.list_media(limit=10)
for m in [next(x for x in media if x.get("media_product_type") == "REELS"), next((x for x in media if x.get("media_type") == "CAROUSEL_ALBUM"), None)]:
    if not m:
        continue
    print("MEDIA", m.get("media_type"), m.get("media_product_type"))
    tries = []
    for metric in ["reach", "views", "likes", "total_interactions"]:
        for b in ["age", "gender", "country", "city", "follow_type", "media_product_type"]:
            tries.append((f"{metric} by {b}", {"metric": metric, "breakdown": b, "metric_type": "total_value"}))
    for metric in ["reached_audience_demographics", "engaged_audience_demographics", "follower_demographics"]:
        tries.append((metric, {"metric": metric, "breakdown": "age", "metric_type": "total_value", "period": "lifetime"}))
    for label, params in tries:
        try:
            out = json.dumps(c._get(f"{m['id']}/insights", params))
            print("OK  ", label, out[:220])
        except InstagramError as e:
            print("FAIL", label, str(e)[:140])
