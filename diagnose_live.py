"""Poll the follower count for a few minutes to see how often Instagram's API value changes.

    python diagnose_live.py [minutes] [seconds_between]
"""
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from ig_client import InstagramClient, InstagramError
from sync import get_token

mins = float(sys.argv[1]) if len(sys.argv) > 1 else 8
gap = float(sys.argv[2]) if len(sys.argv) > 2 else 20
c = InstagramClient(get_token())
c.connect()
user = c._get(c.uid, {"fields": "username"})["username"]
import json, requests
r = requests.get(f"{c.host}/{c.version}/{c.uid}", params={"fields": "followers_count", "access_token": c.token}, timeout=30)
for h in ("x-app-usage", "x-business-use-case-usage", "x-ad-account-usage"):
    if h in r.headers:
        print(f"{h}: {r.headers[h]}", flush=True)
print("status", r.status_code, r.text[:200], flush=True)
last = {}
end = time.time() + mins * 60
while time.time() < end:
    now = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%-I:%M:%S %p")
    row = {}
    try:
        row["direct"] = c._get(c.uid, {"fields": "followers_count"})["followers_count"]
    except InstagramError as e:
        row["direct"] = f"error: {e}"
    try:
        bd = c._get(c.uid, {"fields": f"business_discovery.username({user}){{followers_count}}"})
        row["discovery"] = bd["business_discovery"]["followers_count"]
    except InstagramError as e:
        row["discovery"] = f"error: {e}"
    changed = [k for k in row if last.get(k) not in (None, row[k])]
    print(f"{now}  direct={row['direct']}  business_discovery={row['discovery']}"
          + (f"   <- changed: {', '.join(changed)}" if changed else ""), flush=True)
    last = row
    time.sleep(gap)
