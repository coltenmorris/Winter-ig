"""Which time ranges does Instagram allow for viewer (reached audience) demographics?"""
from ig_client import InstagramClient, InstagramError
from sync import get_token

c = InstagramClient(get_token()); c.connect()
for tf in ["this_week", "this_month", "prev_month", "last_14_days", "last_30_days", "last_90_days", "lifetime", None]:
    params = {"metric": "reached_audience_demographics", "period": "lifetime", "metric_type": "total_value", "breakdown": "gender"}
    if tf:
        params["timeframe"] = tf
    try:
        r = c._get(f"{c.uid}/insights", params)
        res = r["data"][0]["total_value"]["breakdowns"][0]["results"]
        print("OK  ", tf, "total viewers:", sum(x["value"] for x in res))
    except (InstagramError, KeyError, IndexError) as e:
        print("FAIL", tf, str(e)[:150])
