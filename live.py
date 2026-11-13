"""Live follower ticker for the private analytics page (Streamlit only).

Asks Instagram for the current follower count every 5 seconds using the IG_ACCESS_TOKEN
Streamlit secret. The token stays on the server; it is never sent to the browser.
"""
import html
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from ig_client import InstagramClient, InstagramError
from shared import cfg
from sync import clean_token, describe_token

REFRESH_SECONDS = 5
FIRST_MILESTONE, MILESTONE_STEP = 50_000, 5_000  # 50K, 55K, 60K, ...


def milestone_for(n: int | None) -> int | None:
    """Latest follower milestone reached (50,000 and every 5,000 after), or None below 50,000."""
    return n // MILESTONE_STEP * MILESTONE_STEP if n is not None and n >= FIRST_MILESTONE else None
CONFETTI_COLORS = ["#8FAF78", "#E6D49C", "#D3DBCF", "#4E6A47", "#C9A27A", "#B5D69C"]


def confetti_html(milestone: int, nonce: int = 0) -> str:
    """Milestone celebration: the screen dims, the number appears large in the center and confetti rains down.
    Pure CSS, gone in under 5 seconds (before the next refresh). `nonce` makes a replay restart the animation."""
    rnd = random.Random(milestone)
    bits = []
    for _ in range(140):
        w = rnd.uniform(6, 11)
        bits.append(
            f'<i style="left:{rnd.uniform(0, 100):.1f}%;width:{w:.0f}px;height:{w * rnd.uniform(.4, .7):.0f}px;'
            f'background:{rnd.choice(CONFETTI_COLORS)};--dx:{rnd.uniform(-18, 18):.0f}vw;--r:{rnd.uniform(-720, 720):.0f}deg;'
            f'animation-duration:{rnd.uniform(2.6, 3.6):.2f}s;animation-delay:{rnd.uniform(0, .9):.2f}s"></i>')
    # Alternate the wrapper tag on each replay so the browser builds fresh elements and the animation restarts
    tag = "section" if nonce % 2 else "div"
    return (f'<{tag} class="celebrate" data-run="{nonce}"><div class="celebrate-dim" aria-hidden="true"></div>'
            f'<div class="confetti" aria-hidden="true">{"".join(bits)}</div>'
            f'<div class="milestone" role="status"><b>{milestone:,}</b><span>followers on Instagram</span></div></{tag}>')


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
        key = "live_prev_hero" if hero else "live_prev"
        try:
            n = _live_count(token)
        except Exception as e:  # never let the ticker break the page, and never pass an old number off as live
            print(f"[live followers] {type(e).__name__}: {e}", flush=True)  # shows in Manage app > logs
            last = st.session_state.get(key)
            shown = last if last is not None else synced_followers
            why = html.escape(str(e))[:160]
            note = ("last live count" if last is not None else "count from the last daily sync")
            if hero and shown is not None:
                st.markdown(f"""<div class="live-hero"><div class="live-n">{shown:,}</div>
                  <div class="l">followers on Instagram</div>
                  <div class="live-banner paused" role="status"><span class="dot" aria-hidden="true"></span><b>Live tracker paused</b>
                  <span>Showing the {note}, retrying every {REFRESH_SECONDS} seconds</span></div>
                  <div class="live-why">Instagram said: {why}</div></div>""", unsafe_allow_html=True)
            else:
                st.warning(f"Live follower count isn't working. Instagram said: {e}  \n"
                           f"{describe_token(token)} If this doesn't match the IG_ACCESS_TOKEN saved on GitHub, "
                           "paste the GitHub one into this app's Secrets.")
            return
        tick = st.session_state.get(key + "_tick", 0) + 1
        st.session_state[key + "_tick"] = tick
        phase = "a" if tick % 2 else "b"
        start = st.session_state.setdefault("live_start", n)
        prev = st.session_state.get(key, n)
        st.session_state[key] = n
        # Milestone celebration (50K, 55K, 60K, ...): once per milestone per visit, when the count crosses it
        # while watching (or within the first 100 followers past it, so a reload right after still gets it)
        m = milestone_for(n)
        done = st.session_state.setdefault("celebrated", set())
        if m and m not in done and (prev < m or n < m + 100):
            done.add(m)
            st.markdown(confetti_html(m), unsafe_allow_html=True)
        if hero:
            st.markdown(f"""<div class="live-hero">
              <div class="live-n" aria-label="{n:,} followers">{odometer_html(prev, n, phase)}</div>
              <div class="l">followers on Instagram</div>
              <div class="live-banner" role="status"><span class="dot" aria-hidden="true"></span><b>Live tracker</b>
              <span>Updates every {REFRESH_SECONDS} seconds</span></div></div>""",
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
