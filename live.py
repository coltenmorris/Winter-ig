"""Live follower ticker for the private analytics page (Streamlit only).

Asks Instagram for the current follower count every 5 seconds using the IG_ACCESS_TOKEN
Streamlit secret. The token stays on the server; it is never sent to the browser.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from ig_client import InstagramClient, InstagramError
from shared import cfg
from sync import clean_token, describe_token

REFRESH_SECONDS = 5


@st.cache_data(show_spinner=False)
def _account(token: str) -> tuple[str, str]:
    """Look up which API host and Instagram account this token reads, once per token.
    Only plain strings are cached, so a redeploy (which reloads the code) can't leave a stale object behind."""
    c = InstagramClient(token)
    c.connect()
    return c.host, c.uid


@st.cache_data(ttl=REFRESH_SECONDS - 1, show_spinner=False)
def _count(token: str) -> int:
    host, uid = _account(token)
    c = InstagramClient(token)
    c.host, c.uid = host, uid
    return int(c._get(uid, {"fields": "followers_count"})["followers_count"])


def _live_count(token: str) -> int:
    """Current follower count. On a failure, forget the saved account lookup and try once more."""
    try:
        return _count(token)
    except Exception:
        _account.clear()
        return _count(token)


def odometer_html(prev: int, n: int, phase: str = "a") -> str:
    """Follower count where each changed digit moves vertically: the new digit slides in and the old one
    slides out and fades (upward when the count rises, downward when it falls). Nothing is clipped, so the
    digits render whole in any font."""
    new, old = f"{n:,}", f"{prev:,}"
    width = max(len(new), len(old))
    new, old = new.rjust(width), old.rjust(width)
    direction = "up" if n > prev else "down"
    out = []
    for o, c in zip(old, new):
        if c == " ":
            continue  # digit that disappeared (e.g. 1,000 -> 999)
        if not c.isdigit():
            out.append(f'<span class="d sep">{c}</span>')  # comma keeps its natural width
        elif o == c:
            out.append(f'<span class="d">{c}</span>')
        else:
            gone = f'<span class="old" aria-hidden="true">{o}</span>' if o.strip() else ""
            # phase alternates a/b on every refresh so the browser restarts the animation even when the
            # same digit changes on back-to-back refreshes (it reuses the element otherwise)
            out.append(f'<span class="d roll {direction} {phase}">{gone}<span class="new">{c}</span></span>')
    return "".join(out)


def live_followers(synced_followers: int | None, hero: bool = False):
    """Rolling live follower count. hero=True renders it as the media kit's big follower number."""
    token = clean_token(cfg("IG_ACCESS_TOKEN"))
    if not token:
        st.caption("Live follower count: add IG_ACCESS_TOKEN to this app's Secrets to turn it on.")
        return

    @st.fragment(run_every=REFRESH_SECONDS)
    def ticker():
        try:
            n = _live_count(token)
        except Exception as e:  # never let the ticker break the page
            if hero and synced_followers is not None:
                print(f"[live followers] {type(e).__name__}: {e}", flush=True)
                st.markdown(f'<div class="live-hero"><div class="live-n">{synced_followers:,}</div>'
                            f'<div class="l">followers on Instagram</div></div>', unsafe_allow_html=True)
            else:
                print(f"[live followers] {type(e).__name__}: {e}", flush=True)  # shows in Manage app > logs
                st.warning(f"Live follower count isn't working. Instagram said: {e}  \n"
                           f"{describe_token(token)} If this doesn't match the IG_ACCESS_TOKEN saved on GitHub, "
                           "paste the GitHub one into this app's Secrets.")
            return
        key = "live_prev_hero" if hero else "live_prev"
        tick = st.session_state.get(key + "_tick", 0) + 1
        st.session_state[key + "_tick"] = tick
        phase = "a" if tick % 2 else "b"
        start = st.session_state.setdefault("live_start", n)
        prev = st.session_state.get(key, n)
        st.session_state[key] = n
        if hero:
            st.markdown(f"""<div class="live-hero">
              <div class="live-n" aria-label="{n:,} followers">{odometer_html(prev, n, phase)}</div>
              <div class="l"><span class="dot" aria-hidden="true"></span>live followers on Instagram</div></div>""",
                        unsafe_allow_html=True)
            return
        now = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%-I:%M:%S %p")
        bits = []
        if n != start:
            d = n - start
            bits.append(f'<span class="{"up" if d > 0 else ""}">{"&#9650; " if d > 0 else ""}{d:+,}</span> since you opened this page')
        if synced_followers is not None and n != synced_followers:
            d = n - synced_followers
            bits.append(f"{d:+,} since the last daily sync")
        st.markdown(f"""<div class="live glass">
          <div class="live-top"><span class="dot" aria-hidden="true"></span>Live followers</div>
          <div class="live-n" aria-label="{n:,} followers">{odometer_html(prev, n, phase)}</div>
          <div class="live-sub">{" &nbsp;·&nbsp; ".join(bits) if bits else "No change since you opened this page"}<br>
          Updated {now} PT, refreshes every {REFRESH_SECONDS} seconds</div></div>""", unsafe_allow_html=True)

    ticker()
