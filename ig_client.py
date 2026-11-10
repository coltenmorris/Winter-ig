"""Small client for the Instagram API.

Works with both kinds of token Meta hands out:
- Instagram Login tokens (start with "IG") -> graph.instagram.com, account "me"
- Facebook / Unified login tokens (usually "EAA...") -> graph.facebook.com, using the
  Instagram account ID found through your Pages or business portfolio
"""
import os
import requests

IG_HOST = "https://graph.instagram.com"
FB_HOST = "https://graph.facebook.com"
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
        self.host = None   # set by connect()
        self.uid = "me"    # Instagram account ID ("me" on graph.instagram.com)

    def _get(self, path: str, params: dict | None = None, versioned: bool = True, host: str | None = None) -> dict:
        base = host or self.host or IG_HOST
        url = f"{base}/{self.version}/{path}" if versioned else f"{base}/{path}"
        params = dict(params or {})
        params["access_token"] = self.token
        r = requests.get(url, params=params, timeout=30)
        data = r.json() if r.content else {}
        if r.status_code != 200 or "error" in data:
            msg = data.get("error", {}).get("message", r.text)
            raise InstagramError(msg)
        return data

    # ---- connection ----
    def connect(self) -> str:
        """Work out which API this token belongs to and which Instagram account to read."""
        if self.host:
            return self.host
        errors = []
        if self.token.startswith("IG"):
            order = [IG_HOST, FB_HOST]
        else:
            order = [FB_HOST, IG_HOST]
        for host in order:
            try:
                if host == IG_HOST:
                    self._get("me", {"fields": "user_id,username"}, host=IG_HOST)
                    self.host, self.uid = IG_HOST, "me"
                    return host
                self.uid = self._find_fb_ig_account()
                self.host = FB_HOST
                return host
            except InstagramError as e:
                errors.append(f"{host.split('//')[1]}: {e}")
        raise InstagramError("Couldn't connect with this token. " + " | ".join(errors))

    def _find_fb_ig_account(self) -> str:
        tried = []
        # 1) Token issued directly for the Instagram account
        try:
            me = self._get("me", {"fields": "id,username"}, host=FB_HOST)
            if me.get("username"):
                return me["id"]
        except InstagramError as e:
            tried.append(f"account: {e}")
        # 2) Instagram account linked to one of your Facebook Pages (needs pages_show_list)
        try:
            pages = self._get("me/accounts", {"fields": "instagram_business_account{id,username}"}, host=FB_HOST)
            for p in pages.get("data", []):
                if p.get("instagram_business_account"):
                    return p["instagram_business_account"]["id"]
        except InstagramError as e:
            tried.append(f"pages: {e}")
        # 3) Instagram account in your business portfolio (needs business_management)
        try:
            biz = self._get("me/businesses", {"fields": "instagram_business_accounts{id,username},"
                                                       "owned_instagram_accounts{id,username}"}, host=FB_HOST)
            for b in biz.get("data", []):
                for key in ("instagram_business_accounts", "owned_instagram_accounts"):
                    accts = b.get(key, {}).get("data", [])
                    if accts:
                        return accts[0]["id"]
        except InstagramError as e:
            tried.append(f"business portfolio: {e}")
        raise InstagramError("No Instagram account reachable with this token ("
                             + "; ".join(tried) + "). " + self._permission_report())

    def _permission_report(self) -> str:
        try:
            perms = self._get("me/permissions", host=FB_HOST).get("data", [])
            granted = sorted(p["permission"] for p in perms if p.get("status") == "granted")
        except InstagramError:
            return ""
        needed = ["instagram_basic", "instagram_manage_insights", "pages_show_list", "business_management"]
        missing = [p for p in needed if p not in granted]
        out = f"Granted permissions: {', '.join(granted) or 'none'}."
        if missing:
            out += f" Missing: {', '.join(missing)}."
        return out

    # ---- account ----
    def me(self) -> dict:
        self.connect()
        base = "username,followers_count,follows_count,media_count"
        try:
            d = self._get(self.uid, {"fields": base + ",name,biography,profile_picture_url"})
        except InstagramError:
            d = self._get(self.uid, {"fields": base})
        d["api"] = "Instagram Login" if self.host == IG_HOST else "Facebook/Unified login"
        return d

    def account_daily(self) -> dict:
        """Yesterday's account-wide totals (reach, views, accounts engaged, interactions)."""
        out = {}
        for m in ["reach", "views", "accounts_engaged", "total_interactions"]:
            try:
                out.update(self._parse(self._get(f"{self.uid}/insights", {
                    "metric": m, "period": "day", "metric_type": "total_value"})))
            except InstagramError:
                pass
        return out

    def demographics(self) -> dict:
        """Follower breakdowns by age, gender, country, city. Needs 100+ followers."""
        out = {}
        for b in ["age", "gender", "country", "city"]:
            try:
                resp = self._get(f"{self.uid}/insights", {
                    "metric": "follower_demographics", "period": "lifetime",
                    "metric_type": "total_value", "timeframe": "this_month", "breakdown": b})
                rows = resp["data"][0]["total_value"]["breakdowns"][0]["results"]
                out[b] = {r["dimension_values"][0]: r["value"] for r in rows}
            except (InstagramError, KeyError, IndexError):
                pass
        return out

    # ---- media ----
    def list_media(self, limit: int | None = None) -> list[dict]:
        self.connect()
        fields = list(MEDIA_FIELDS)
        items: list[dict] = []
        try:
            page = self._get(f"{self.uid}/media", {"fields": ",".join(fields), "limit": 50})
        except InstagramError as e:
            # Some fields are only available on certain login types; retry without them.
            if "media_product_type" in str(e) or "nonexisting field" in str(e).lower():
                fields.remove("media_product_type")
                page = self._get(f"{self.uid}/media", {"fields": ",".join(fields), "limit": 50})
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
        self.connect()
        if self.host != IG_HOST:
            raise InstagramError("automatic refresh only works for Instagram Login tokens; "
                                 "generate a new token in the Meta dashboard before it expires")
        data = self._get("refresh_access_token", {"grant_type": "ig_refresh_token"}, versioned=False, host=IG_HOST)
        self.token = data["access_token"]
        return self.token
