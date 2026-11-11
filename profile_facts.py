"""General account facts for the media kit: location and how long the account has been around.

Instagram's API doesn't share an account's location or creation date, so they come from settings
(ACCOUNT_LOCATION, ACCOUNT_CREATED, copied from Instagram's "About this account" screen), falling
back to the pin location in the bio and the date of the earliest post.
"""
import re
from datetime import datetime


def bio_location(bio: str | None) -> str | None:
    """Text after a pin emoji in the bio, e.g. "los angeles/malibu" -> "Los Angeles/Malibu"."""
    if not bio:
        return None
    m = re.search(r"(?:\U0001F4CD|\U0001F4CC)\s*([^\n|•]+)", bio)
    if not m:
        return None
    loc = m.group(1).strip(" ,.-")
    return re.sub(r"[A-Za-z]+", lambda w: w.group(0).capitalize() if w.group(0).islower() else w.group(0), loc) or None


def facts(location_setting: str | None, created_setting: str | None, bio: str | None,
          first_post: datetime | None) -> list[tuple[str, str]]:
    out = []
    loc = (location_setting or "").strip() or bio_location(bio)
    if loc:
        out.append(("Based in", loc))
    if (created_setting or "").strip():
        out.append(("On Instagram since", created_setting.strip()))
    elif first_post is not None:
        out.append(("Posting since", first_post.strftime("%B %Y")))
    return out
