"""Small client for the Instagram API with Instagram Login (graph.instagram.com)."""
import os
import requests

BASE = "https://graph.instagram.com"
API_VERSION = os.getenv("IG_API_VERSION", "v26.0")

# Metrics we try to pull for every video. Instagram rejects the whole request if
# any one metric is unsupported for that media type, so we fall back to
# requesting them one at a time when that happens.
VIDEO_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
]
REELS_ONLY_METRICS = [
    "ig_reels_avg_watch_time",      # milliseconds
    "ig_reels_video_view_total_time",  # milliseconds
    "reels_skip_rate",
    "reposts",
]

MEDIA_FIELDS = [
    "id", "caption", "media_type", "media_product_type", "timestamp",
    "permalink", "thumbnail_url", "like_count", "comments_count",
]


class InstagramError(Exception):
    pass


class InstagramClient:
    def __init__(self, token: str, version: str = API_VERSION):
        if not token:
            raise InstagramError("No access token set. Add IG_ACCESS_TOKEN to your .env file.")
        self.token = token
        self.version = version

    def _get(self, path: str, params: dict | None = None, versioned: bool = True) -> dict:
        url = f"{BASE}/{self.version}/{path}" if versioned else f"{BASE}/{path}"
        params = dict(params or {})
        params["access_token"] = self.token
        r = requests.get(url, params=params, timeout=30)
        data = r.json() if r.content else {}
        if r.status_code != 200 or "error" in data:
            msg = data.get("error", {}).get("message", r.text)
            raise InstagramError(msg)
        return data

    # ---- account ----
    def me(self) -> dict:
        base = "user_id,username,account_type,followers_count,follows_count,media_count"
        try:
            return self._get("me", {"fields": base + ",name,biography,profile_picture_url"})
        except InstagramError:
            return self._get("me", {"fields": base})

    def account_daily(self) -> dict:
        """Yesterday's account-wide totals (reach, views, accounts engaged, interactions)."""
        out = {}
        for m in ["reach", "views", "accounts_engaged", "total_interactions"]:
            try:
                out.update(self._parse(self._get("me/insights", {
                    "metric": m, "period": "day", "metric_type": "total_value"})))
            except InstagramError:
                pass
        return out

    def demographics(self) -> dict:
        """Follower breakdowns by age, gender, country, city. Needs 100+ followers."""
        out = {}
        for b in ["age", "gender", "country", "city"]:
            try:
                resp = self._get("me/insights", {
                    "metric": "follower_demographics", "period": "lifetime",
                    "metric_type": "total_value", "timeframe": "this_month", "breakdown": b})
                rows = resp["data"][0]["total_value"]["breakdowns"][0]["results"]
                out[b] = {r["dimension_values"][0]: r["value"] for r in rows}
            except (InstagramError, KeyError, IndexError):
                pass
        return out

    # ---- media ----
    def list_media(self, limit: int | None = None) -> list[dict]:
        fields = list(MEDIA_FIELDS)
        items: list[dict] = []
        try:
            page = self._get("me/media", {"fields": ",".join(fields), "limit": 50})
        except InstagramError as e:
            # Some fields are only available on certain login types; retry without them.
            if "media_product_type" in str(e) or "nonexisting field" in str(e).lower():
                fields.remove("media_product_type")
                page = self._get("me/media", {"fields": ",".join(fields), "limit": 50})
            else:
                raise
        while True:
            items.extend(page.get("data", []))
            if limit and len(items) >= limit:
                return items[:limit]
            nxt = page.get("paging", {}).get("next")
            if not nxt:
                return items
            r = requests.get(nxt, timeout=30)
            page = r.json()
            if "error" in page:
                raise InstagramError(page["error"].get("message"))

    def media_insights(self, media_id: str, is_reel: bool) -> dict:
        metrics = VIDEO_METRICS + (REELS_ONLY_METRICS if is_reel else [])
        try:
            return self._parse(self._get(f"{media_id}/insights", {"metric": ",".join(metrics)}))
        except InstagramError:
            # Fall back to one metric at a time so one bad metric doesn't lose the rest.
            out = {}
            for m in metrics:
                try:
                    out.update(self._parse(self._get(f"{media_id}/insights", {"metric": m})))
                except InstagramError:
                    pass
            return out

    @staticmethod
    def _parse(resp: dict) -> dict:
        out = {}
        for row in resp.get("data", []):
            if row.get("values"):
                out[row["name"]] = row["values"][0].get("value")
            elif row.get("total_value"):
                out[row["name"]] = row["total_value"].get("value")
        return out

    # ---- token ----
    def refresh_token(self) -> str:
        """Extend the long-lived token another 60 days. Token must be at least 24h old."""
        data = self._get("refresh_access_token", {"grant_type": "ig_refresh_token"}, versioned=False)
        self.token = data["access_token"]
        return self.token
