"""Show what Instagram returns right now for viewer/follower demographics, by timeframe."""
from ig_client import InstagramClient
from sync import get_token

c = InstagramClient(get_token())
c.connect()
for metric in ("reached_audience_demographics", "engaged_audience_demographics", "follower_demographics"):
    for tf in ("this_week", "this_month"):
        g = c.demographics(metric, tf).get("gender", {})
        tot = sum(g.values())
        print(f"{metric:32} {tf:11} total={tot:>11,}  " + "  ".join(f"{k}={v / tot:.1%}" for k, v in sorted(g.items())) if tot else f"{metric} {tf}: nothing")
print("errors:", c.insight_errors[:3] if hasattr(c, "insight_errors") else None)
