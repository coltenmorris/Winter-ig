"""Shared data loading, metrics, config and styling for both pages."""
import html
import os
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import db
import flags as flags_mod

LOCAL_TZ = "America/Los_Angeles"  # all dates and times on the dashboard are Pacific

# ---------------- palette (overgrown: forest dark, moss, mist, stone, one lamp accent) ----------------
ABYSS = "#0E1411"    # page
CANOPY = "#141C17"   # panels
IVY = "#24302A"      # low fills, tracks
MOSSD = "#4E6A47"    # mid data
FERNB = "#8FAF78"    # primary data
MIST = "#D3DBCF"     # text
STONE = "#8B9589"    # secondary text
LAMP = "#E6D49C"     # best performers only
RULE_C = "rgba(211,219,207,.14)"
# names used by the pages: bright data = MOSS, mid = SAGE, low = FERN, accent = SAND
MOSS, SAGE, FERN, SAND, OAT, BARK, DUSK = FERNB, MOSSD, "#2E4030", LAMP, ABYSS, MIST, STONE
LINE, GLASS = RULE_C, CANOPY
NAVY, LANE, SPLIT, RULE, SLATE, INK, CHALK = MOSS, SAGE, SAND, IVY, STONE, MIST, ABYSS


def cfg(key: str, default: str = "") -> str:
    """Read a setting from Streamlit secrets, then environment variables."""
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


# ---------------- data ----------------
def load():
    # Re-read whenever the database or the tag file changes.
    mt = lambda p: p.stat().st_mtime if p.exists() else 0
    return _load(mt(db.DB_PATH) + mt(flags_mod.FLAGS_PATH))


@st.cache_data(ttl=300)
def _load(_mtime: float):
    conn = db.connect()
    q = lambda sql: pd.read_sql(sql, conn)
    media, snaps = q("SELECT * FROM media"), q("SELECT * FROM media_snapshots")
    acct = q("SELECT * FROM account_snapshots ORDER BY captured_date")
    daily = q("SELECT * FROM account_daily ORDER BY captured_date")
    demo = q("SELECT * FROM demographics")
    profile = {k[len("profile_"):]: v for k, v in
               conn.execute("SELECT key, value FROM settings WHERE key LIKE 'profile_%'").fetchall()}
    conn.close()
    for df in (snaps, acct, daily):
        df["captured_date"] = pd.to_datetime(df["captured_date"])
    snaps = clean_snaps(snaps)
    media["posted_at"] = pd.to_datetime(media["posted_at"], utc=True).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    fl = flags_mod.load_flags()
    media["is_trial"] = media["id"].isin(fl["trial"]).astype(int) | media["is_trial"].fillna(0).astype(int)
    media["is_ad"] = media["id"].isin(list(fl["ads"])).astype(int)
    media["brand"] = media["id"].map(lambda i: fl["ads"].get(i, {}).get("brand", ""))
    return media, snaps, acct, daily, demo, profile


def clean_snaps(s: pd.DataFrame) -> pd.DataFrame:
    """Instagram sometimes returns 0 for metrics it doesn't supply. Treat impossible zeros as missing
    and rebuild total interactions from its parts so engagement is never understated."""
    if s.empty:
        return s
    s = s.copy()
    has_views = s["views"].fillna(0) > 0
    for col in ("reach", "avg_watch_ms", "total_watch_ms", "skip_rate"):
        s.loc[has_views & (s[col].fillna(0) == 0), col] = None
    s.loc[(s["likes"].fillna(0) > 0) & (s["saved"].fillna(0) == 0) & (s["reach"].isna()), "saved"] = None
    parts = s[["likes", "comments", "shares", "saved"]].fillna(0).sum(axis=1)
    s["total_interactions"] = pd.concat([s["total_interactions"].fillna(0), parts], axis=1).max(axis=1)
    return s


def video_table(media: pd.DataFrame, snaps: pd.DataFrame, window_days: int = 7) -> pd.DataFrame:
    """One row per video with latest stats, views gained in the window, and derived rates."""
    if snaps.empty:
        return pd.DataFrame()
    snaps = snaps.sort_values(["media_id", "captured_date"])
    latest = snaps.groupby("media_id").tail(1).set_index("media_id")
    cutoff = snaps["captured_date"].max() - pd.Timedelta(days=window_days)
    before = (snaps[snaps["captured_date"] <= cutoff].groupby("media_id").tail(1)
              .set_index("media_id").reindex(latest.index).fillna(0))
    t = media.set_index("id").join(latest, how="inner")
    t["views_gained"] = latest["views"] - before["views"]
    inter = t[["likes", "comments", "shares", "saved"]].fillna(0).sum(axis=1)
    t["total_interactions"] = t["total_interactions"].fillna(inter)
    t["engagement_rate"] = (t["total_interactions"] / t["views"].where(t["views"] > 0)).astype(float)
    t["avg_watch_s"] = t["avg_watch_ms"] / 1000
    t["title"] = (t["caption"].fillna("Untitled").str.split("\n").str[0]
                  .str.replace(r"#\w+", "", regex=True).str.strip().str.slice(0, 48))
    t["title"] = t["title"].where(t["title"] != "", "Untitled")
    t["kind"] = [db.media_kind(a, b) for a, b in zip(t["media_type"], t["product_type"])]
    t["hashtags"] = t["caption"].fillna("").str.findall(r"#(\w+)").apply(lambda x: [h.lower() for h in x])
    # Age in fractional days, both sides in Pacific time (matches the GitHub site exactly)
    t["age_days"] = (pd.Timestamp.now(tz=LOCAL_TZ).tz_localize(None) - t["posted_at"]).dt.total_seconds() / 86400
    return t


def fmt_num(n) -> str:
    if n is None or pd.isna(n):
        return "n/a"
    n = float(n)
    for div, suf in ((1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{suf}".replace(".0" + suf, suf)
    return f"{n:,.0f}"


# ---------------- styling (neo-Swiss) ----------------
FONT = "Schibsted Grotesk"
FONT_DISPLAY = FONT


THERMAL_CSS = (Path(__file__).parent / "thermal.css").read_text()


def thermal_background():
    """Moving thermal gradient behind every page, or a plain color when switched off at the bottom."""
    moving = st.session_state.get("bg_moving", True)
    st.markdown(f"<style>{THERMAL_CSS}"
                + ("" if moving else ".thermal { display: none; }")
                + '[data-testid="stMain"], [data-testid="stHeader"] { position: relative; z-index: 1; }</style>'
                + '<div class="thermal" aria-hidden="true"><i></i><i></i><i></i></div>',
                unsafe_allow_html=True)


def background_switch():
    st.toggle("Moving background", value=True, key="bg_moving",
              help="Turn off for a plain static background color.")


def inject_css():
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap');
html, body, [class*="st-"], .stMarkdown, button, input, textarea, select {{ font-family: '{FONT}', 'Helvetica Neue', Arial, sans-serif; }}
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {{ font-family: 'Material Symbols Rounded' !important; }}
.stApp {{ background: {ABYSS}; color: {MIST}; font-feature-settings: "tnum" 1; }}
.stApp::before {{ content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background: radial-gradient(50% 38% at 62% -6%, rgba(211,219,207,.10), transparent 70%),
              radial-gradient(40% 30% at 8% 100%, rgba(78,106,71,.16), transparent 70%); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: {CANOPY}; border-right: 1px solid {RULE_C}; }}
.block-container {{ max-width: 1120px; padding-top: 2.4rem; padding-bottom: 4.5rem; position: relative; z-index: 1; }}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ overflow-x: hidden; max-width: 100vw; }}
img {{ max-width: 100%; }}
p, li, label, span, div {{ color: inherit; }}

h1, h2, h3 {{ font-family: '{FONT}', sans-serif !important; color: {MIST} !important; font-weight: 700 !important; letter-spacing: -.035em; }}
h1 {{ font-size: clamp(2.6rem, 7vw, 5rem) !important; line-height: .92 !important; letter-spacing: -.05em; }}
h2 {{ font-size: clamp(2rem, 4.4vw, 3.2rem) !important; line-height: 1 !important; margin: 4rem 0 .5rem !important;
      padding-top: 16px !important; border-top: 1px solid {RULE_C}; }}
h3 {{ font-size: 1.05rem !important; letter-spacing: -.01em; font-weight: 600 !important; }}
.lede {{ color: {STONE}; margin: 0 0 1.3rem; max-width: 60ch; }}
a {{ color: {FERNB}; }}
:focus-visible {{ outline: 2px solid {LAMP} !important; outline-offset: 3px; }}
.glass {{ background: {CANOPY}; border: 1px solid {RULE_C}; }}
.stripes, .px, .script {{ display: none; }}

/* Hero */
.hero {{ display:grid; grid-template-columns: 7fr 5fr; gap: 0 32px; align-items: end; }}
.hero .id {{ order: 1; background: none !important; border: 0 !important; padding: 0; }}
.hero .count {{ order: 2; background: none !important; border: 0 !important; text-align: right; padding: 0 0 6px; }}
.hero .id h1 {{ font-size: clamp(3rem, 8.2vw, 6.6rem) !important; line-height: .9 !important; letter-spacing: -.055em; margin: 0 !important; padding: 0 !important; }}
.hero .id .row {{ display:flex; align-items:center; gap: 14px; margin-top: 22px; }}
.hero .id .handle {{ color: {STONE}; font-weight: 500; }}
.hero .id .bio {{ margin-top: 14px; max-width: 42ch; white-space: pre-line; }}
.hero .avatar {{ width:44px; height:44px; border-radius:50%; object-fit:cover; order:-1; border:1px solid {RULE_C};
    display:flex; align-items:center; justify-content:center; background:{IVY}; color:{MIST}; font-weight:700; }}
.hero .count .n {{ font-size: clamp(4rem, 11vw, 9rem); font-weight: 800; line-height: .82; letter-spacing: -.06em; color: {FERNB}; }}
.hero .count .l {{ color: {STONE}; margin-top: 12px; font-weight: 500; }}
.contact {{ display:inline-block; margin-top: 22px; background: {MIST}; color: {ABYSS} !important; padding: 11px 20px;
    text-decoration: none !important; font-weight: 600; }}
.contact:hover {{ background: {LAMP}; }}

.created {{ color:{STONE}; font-weight: 500; margin-top: 10px; }}

/* Stats board */
.board {{ display:grid; grid-template-columns: repeat(4, 1fr); margin-top: 44px; background: none !important;
    border: 0 !important; border-top: 1px solid {RULE_C} !important; border-bottom: 1px solid {RULE_C} !important; }}
.board > div {{ padding: 18px 20px 20px 0; min-width: 0; }}
.board > div + div {{ padding-left: 20px; border-left: 1px solid {RULE_C}; }}
.board .v {{ font-size: clamp(2rem, 4vw, 3.1rem); font-weight: 700; line-height: 1; letter-spacing: -.045em; color: {MIST}; }}
.board .k {{ color: {STONE}; font-size: .9rem; margin-top: 10px; }}
.board.five {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }}
.board.five .v {{ font-size: clamp(1.8rem, 3.2vw, 2.7rem); }}
.board .d {{ color: {FERNB}; font-size: .85rem; margin-top: 4px; }}

/* Reel cards */
.reels {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 28px 20px; align-items: start; }}
.reel {{ text-decoration:none !important; color:{MIST} !important; display:block; }}
.reel .thumb {{ aspect-ratio: 4/5; position: relative; overflow:hidden; background: linear-gradient(180deg, #1C2620, #0F1612) !important; border: 0; }}
.reel .thumb img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.reel .thumb .ph {{ position:absolute; inset:auto 14px 14px 14px; color:{MIST}; font-weight: 700; font-size: 1.2rem; line-height: 1.1; letter-spacing: -.03em; }}
.reel .best {{ position:absolute; top:0; left:0; background:{LAMP}; color:{ABYSS}; font-size:.78rem; font-weight:700; padding: 5px 10px; border: 0; }}
.reel .card {{ background: none !important; border: 0 !important; border-top: 1px solid {RULE_C} !important; margin-top: 10px; }}
.reel .meta {{ display:flex; justify-content: space-between; padding: 10px 0 2px; }}
.reel .meta b {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -.04em; line-height: 1; display:block; color: {MIST}; }}
.reel .meta span {{ color:{STONE}; font-size:.82rem; }}
.reel .t {{ padding: 6px 0 0; color:{STONE}; font-size:.9rem; }}

/* Bars */
.panel {{ padding: 18px 20px 20px; }}
.bars .row {{ display:grid; grid-template-columns: 9rem 1fr 3.4rem; gap: 14px; align-items:center; margin: 10px 0; }}
.bars .lbl {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.bars .track {{ height: 4px; background: {IVY}; }}
.bars .fill {{ height:100%; background: {FERNB}; }}
.bars .pct {{ text-align:right; color:{STONE}; font-size:.92rem; }}
.bars.mom .row {{ grid-template-columns: 9rem 1fr 3.2rem 5.2rem; }}
.chg {{ color:{STONE}; font-size:.82rem; text-align:right; white-space:nowrap; margin-left: 6px; }}
.up {{ color: #7CC47F; margin-right: 4px; }}
.lm {{ color:{STONE}; font-size:.85rem; margin-top: 6px; }}
.split {{ display:flex; height: 6px; margin: 10px 0 10px; }}
.legend {{ color:{STONE}; font-size:.9rem; }}
.legend i {{ display:inline-block; width:10px; height:10px; margin-right:6px; }}
.foot {{ color:{STONE}; font-size:.85rem; margin-top: 4.5rem; padding-top: 14px; border-top:1px solid {RULE_C}; }}

/* Streamlit widgets */
[data-testid="stMetric"] {{ background: none; border: 0; border-top: 1px solid {RULE_C}; padding: 14px 0 6px; }}
[data-testid="stMetricValue"] {{ color:{MIST}; font-weight: 700; letter-spacing: -.045em; font-size: 2.4rem; }}
[data-testid="stMetricLabel"] {{ color:{STONE}; }}
[data-testid="stVegaLiteChart"] {{ box-sizing: border-box; overflow: hidden; background:{CANOPY}; border:1px solid {RULE_C}; padding:0; }}
.stButton > button {{ border-radius: 0; background: {MIST}; color: {ABYSS}; border: 0; font-weight: 600; }}
.stButton > button:hover {{ background: {LAMP}; color: {ABYSS}; }}
[data-baseweb="select"] > div, [data-baseweb="input"] > div {{ border-radius: 0 !important; background: {CANOPY} !important; border-color: {RULE_C} !important; }}
[data-testid="stExpander"] details {{ border-radius: 0; border-color: {RULE_C}; background: {CANOPY}; }}
[data-testid="stPageLink"] a span {{ color: {STONE}; font-weight: 500; }}
[data-testid="stDialog"] [role="dialog"] {{ background: {CANOPY}; border: 1px solid {RULE_C}; border-radius: 0; color: {MIST}; }}

/* Reel pop-up */
.reelhead {{ display:grid; grid-template-columns: 96px 1fr; gap: 18px; align-items:start; margin-bottom: 16px; }}
.reelhead img, .reelhead .noimg {{ width:96px; aspect-ratio: 4/5; object-fit:cover; background: linear-gradient(180deg, #1C2620, #0F1612); }}
.reelhead .when {{ color:{STONE}; font-size:.9rem; }}
.reelhead .cap {{ margin: 6px 0 8px; overflow-wrap:anywhere; }}
table.ms {{ width:100%; border-collapse: collapse; table-layout: fixed; }}
table.ms th, table.ms td {{ padding: 9px 6px; border-bottom: 1px solid {RULE_C}; text-align:right; }}
table.ms thead th {{ color:{STONE}; font-weight:500; font-size:.82rem; vertical-align:bottom; }}
table.ms tbody th {{ text-align:left; font-weight:400; color:{MIST}; }}
table.ms th:first-child {{ width: 34%; padding-left: 0; }}
table.ms td {{ font-size: 1.15rem; font-weight: 700; letter-spacing: -.03em; color:{MIST}; }}
table.ms .na {{ font-size:.78rem; font-weight: 400; color:{STONE}; letter-spacing: 0; }}
.note {{ color:{STONE}; font-size:.82rem; margin-top:10px; }}

/* Calendar day list & summaries */
.daycard {{ display:grid; grid-template-columns: 84px 1fr; gap: 16px; padding: 14px 0; background: none !important; border: 0 !important; border-bottom: 1px solid {RULE_C} !important; }}
.daycard img, .daycard .noimg {{ width:84px; aspect-ratio:4/5; object-fit:cover; background: linear-gradient(180deg, #1C2620, #0F1612); }}
.daycard .when {{ color:{STONE}; font-size:.85rem; }}
.daycard .cap {{ margin-top: 4px; overflow-wrap:anywhere; }}
.daycard .stats {{ margin-top: 8px; color:{STONE}; font-size:.88rem; }}
.daycard .stats b {{ color:{MIST}; font-weight:700; }}
.cal-legend {{ display:flex; gap: 16px; align-items:center; color:{STONE}; font-size:.85rem; flex-wrap: wrap; margin: 4px 0 10px; }}
.cal-legend i {{ display:inline-block; width:12px; height:12px; margin-right:6px; vertical-align:-1px; }}
.summary {{ display:flex; flex-wrap:wrap; gap: 6px 32px; color:{STONE}; margin: 14px 0; }}
.summary b {{ font-size:1.6rem; font-weight:700; letter-spacing:-.04em; color:{MIST}; margin-right:6px; }}

/* Live follower ticker */
[data-testid="stToggle"] label p, [data-testid="stCheckbox"] label p {{ color:{STONE}; font-size:.85rem; }}
.live {{ padding: 18px 22px; margin: 6px 0 18px; }}
.live-top {{ color:{STONE}; font-size:.85rem; font-weight:500; display:flex; align-items:center; gap:8px; }}
.live .dot {{ width:8px; height:8px; border-radius:50%; background:#7CC47F; box-shadow: 0 0 0 0 rgba(124,196,127,.6); animation: livepulse 2s infinite; }}
@keyframes livepulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(124,196,127,.55); }} 70% {{ box-shadow: 0 0 0 9px rgba(124,196,127,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(124,196,127,0); }} }}
@media (prefers-reduced-motion: reduce) {{ .live .dot {{ animation: none; }} }}
.live-n {{ font-size: clamp(3rem, 9vw, 5.6rem); font-weight: 800; letter-spacing: -.055em; line-height: 1.15; padding: .04em 0 .08em; color:{FERNB};
           font-variant-numeric: tabular-nums; margin-top: 6px; }}
/* Odometer: changed digits move vertically. No clipping anywhere, so digits always render whole. */
.live-n {{ display:flex; align-items:baseline; }}
.live-n .d, .live-n .d span {{ color:{FERNB} !important; }}
.live-n .d {{ display:inline-block; position:relative; }}
.live-n .d.sep {{ font-feature-settings: "tnum" 0, "pnum" 1; font-variant-numeric: proportional-nums; }}
.live-n .roll .new {{ display:inline-block; }}
.live-n .roll .old {{ position:absolute; left:0; top:0; pointer-events:none; }}
.live-n .roll.up.a .new {{ animation: in-up-a .75s cubic-bezier(.2,.8,.2,1) both, flash-a 1.8s ease-out both; }}
.live-n .roll.up.b .new {{ animation: in-up-b .75s cubic-bezier(.2,.8,.2,1) both, flash-b 1.8s ease-out both; }}
.live-n .roll.up.a .old {{ animation: out-up-a .75s cubic-bezier(.2,.8,.2,1) both; }}
.live-n .roll.up.b .old {{ animation: out-up-b .75s cubic-bezier(.2,.8,.2,1) both; }}
.live-n .roll.down.a .new {{ animation: in-down-a .75s cubic-bezier(.2,.8,.2,1) both; }}
.live-n .roll.down.b .new {{ animation: in-down-b .75s cubic-bezier(.2,.8,.2,1) both; }}
.live-n .roll.down.a .old {{ animation: out-down-a .75s cubic-bezier(.2,.8,.2,1) both; }}
.live-n .roll.down.b .old {{ animation: out-down-b .75s cubic-bezier(.2,.8,.2,1) both; }}
@keyframes in-up-a {{ from {{ transform: translateY(.55em); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
@keyframes in-up-b {{ from {{ transform: translateY(.55em); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
@keyframes out-up-a {{ from {{ transform: none; opacity: 1; }} to {{ transform: translateY(-.55em); opacity: 0; }} }}
@keyframes out-up-b {{ from {{ transform: none; opacity: 1; }} to {{ transform: translateY(-.55em); opacity: 0; }} }}
@keyframes in-down-a {{ from {{ transform: translateY(-.55em); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
@keyframes in-down-b {{ from {{ transform: translateY(-.55em); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
@keyframes out-down-a {{ from {{ transform: none; opacity: 1; }} to {{ transform: translateY(.55em); opacity: 0; }} }}
@keyframes out-down-b {{ from {{ transform: none; opacity: 1; }} to {{ transform: translateY(.55em); opacity: 0; }} }}
@keyframes flash-a {{ from {{ filter: brightness(1.45); }} to {{ filter: brightness(1); }} }}
@keyframes flash-b {{ from {{ filter: brightness(1.45); }} to {{ filter: brightness(1); }} }}
@media (prefers-reduced-motion: reduce) {{
  .live-n .roll .new {{ animation: none !important; }}
  .live-n .roll .old {{ display: none; }}
}}
/* Live count in the media kit hero, in place of the big follower number */
.hero.solo {{ grid-template-columns: 1fr; }}
.live-hero {{ text-align:right; padding: 0 0 6px; }}
.live-hero .live-n {{ justify-content:flex-end; font-size: clamp(4rem, 11vw, 9rem); font-weight: 800; letter-spacing: -.06em;
                      line-height: 1.15 !important; padding: .06em 0 .1em; overflow: visible; }}
[data-testid="stMarkdownContainer"]:has(.live-hero), [data-testid="stMarkdownContainer"]:has(.live) {{ overflow: visible !important; }}
.live-hero .l {{ color:{STONE}; margin-top: 4px; font-weight: 500; display:flex; gap:8px; align-items:center; justify-content:flex-end; }}
.live-hero .dot {{ width:8px; height:8px; border-radius:50%; background:#7CC47F; animation: livepulse 2s infinite; }}
.live-banner {{ display:inline-flex; flex-wrap:wrap; align-items:center; gap:6px 10px; padding: 8px 14px; margin-bottom: 18px;
  border: 1px solid rgba(124,196,127,.35); background: rgba(124,196,127,.08); color:{MIST}; font-size:.9rem; }}
.live-banner b {{ font-weight: 700; }}
.live-banner span:not(.dot) {{ color:{STONE}; }}
.live-banner .dot {{ width:8px; height:8px; border-radius:50%; background:#7CC47F; animation: livepulse 2s infinite; }}
@media (prefers-reduced-motion: reduce) {{ .live-hero .dot, .live-banner .dot {{ animation: none; }} }}
@media (max-width: 760px) {{ .live-hero {{ text-align:left; }} .live-hero .live-n, .live-hero .l {{ justify-content:flex-start; }} }}
.live-sub {{ color:{STONE}; font-size:.85rem; margin-top: 8px; line-height:1.5; }}

/* Period summary */
.ps {{ display:grid; grid-template-columns: minmax(0,1.6fr) repeat(5, minmax(0,1fr)); gap: 0 12px; align-items:center;
       padding: 11px 16px; border-bottom: 1px solid {RULE_C}; font-variant-numeric: tabular-nums; }}
.ps.head {{ color:{STONE}; font-size:.82rem; font-weight: 500; }}
.ps .n {{ text-align:right; }}
.ps small {{ display:block; color:{FERNB}; font-size:.78rem; }}
.ps .na {{ color:{STONE}; }}

/* Reel list */
.rl {{ display:grid; grid-template-columns: 1fr repeat(4, 5.2rem); gap: 0 12px; align-items:center;
       padding: 12px 16px; border-bottom: 1px solid {RULE_C}; }}
.rl.head {{ color:{STONE}; font-size:.82rem; font-weight: 500; }}
.rl .t {{ overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }}
.rl .t small {{ color:{STONE}; display:block; }}
.rl .n {{ text-align:right; }}
.rl .trial {{ font-size:.72rem; font-weight: 600; background:{LAMP}; color:{ABYSS}; padding:1px 6px; margin-left:8px; }}

@media (max-width: 760px) {{
  .hero {{ grid-template-columns: 1fr; }}
  .hero .count {{ order: 0; text-align: left; padding-bottom: 22px; }}
  .board {{ grid-template-columns: repeat(2, 1fr); }}
  .board > div:nth-child(3) {{ border-left:none; padding-left: 0; }}
  .board > div:nth-child(n+3) {{ border-top: 1px solid {RULE_C}; }}
  .board.five {{ grid-template-columns: repeat(2, 1fr); }}
  .board.five > div:nth-child(5) {{ grid-column: span 2; border-left: none; padding-left: 0; }}
  .reels {{ grid-template-columns: repeat(2, minmax(0,1fr)); gap: 22px 12px; }}
  .bars .row {{ grid-template-columns: 7rem 1fr 2.8rem; }}
  .bars.mom .row {{ grid-template-columns: 6rem 1fr 2.6rem 4.6rem; }}
  .rl {{ grid-template-columns: 1fr 4.4rem 4.4rem; }}
  .ps {{ grid-template-columns: minmax(0,1.5fr) repeat(3, minmax(0,1fr)); padding: 10px 12px; font-size: .88rem; }}
  .ps .hide-sm {{ display:none; }}
  .rl .hide-sm {{ display:none; }}
  table.ms th, table.ms td {{ padding: 8px 3px; font-size:.82rem; }}
  table.ms td {{ font-size: .98rem; }}
}}
/* stories */
.sday {{ margin-top: 26px; }}
.sday-h {{ display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: baseline; padding-bottom: 10px; border-bottom: 1px solid {RULE_C}; }}
.sday-h span {{ color: {STONE}; font-size: .92rem; }}
.sgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(132px, 1fr)); gap: 18px 14px; margin-top: 14px; }}
.sthumb {{ aspect-ratio: 9 / 16; position: relative; overflow: hidden; background: linear-gradient(180deg, #1C2620, #0F1612); }}
.sthumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.scard .st-t {{ color: {STONE}; font-size: .82rem; margin-top: 8px; }}
.scard .st-v {{ font-weight: 700; font-size: 1.15rem; letter-spacing: -.02em; }}
.scard .st-v span {{ font-weight: 400; font-size: .8rem; color: {STONE}; letter-spacing: 0; }}
.scard dl {{ display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; margin: 6px 0 0; font-size: .82rem; }}
.scard dt {{ color: {STONE}; }} .scard dd {{ margin: 0; text-align: right; font-variant-numeric: tabular-nums; }}
.board.four {{ grid-template-columns: repeat(4, 1fr); }}
/* Section rail: hover near the left edge (mouse/trackpad screens only) */
.rail-zone, .rail {{ display: none; }}
@media (hover: hover) and (pointer: fine) and (min-width: 900px) {{
  .rail-zone {{ display: block; position: fixed; left: 0; top: 0; bottom: 0; width: 40px; z-index: 990; }}
  .rail {{ display: flex; flex-direction: column; gap: 2px; position: fixed; left: 14px; top: 50%; z-index: 991;
    transform: translate(-12px, -50%); opacity: 0; pointer-events: none; transition: opacity .2s ease, transform .2s ease;
    padding: 12px; background: rgba(20, 28, 23, .55); border: 1px solid {RULE_C};
    -webkit-backdrop-filter: blur(14px) saturate(1.2); backdrop-filter: blur(14px) saturate(1.2); }}
  .rail-zone:hover + .rail, .rail:hover, .rail:focus-within {{ opacity: 1; pointer-events: auto; transform: translate(0, -50%); }}
  .rail a {{ display: block; padding: 7px 12px; color: {STONE} !important; text-decoration: none !important; font-size: .88rem;
    font-weight: 500; white-space: nowrap; }}
  .rail a:hover {{ color: {MIST} !important; background: rgba(211, 219, 207, .06); }}
}}
@media (prefers-reduced-motion: reduce) {{ .rail {{ transition: none; }} }}
h2 {{ scroll-margin-top: 24px; }}
</style>""", unsafe_allow_html=True)
    thermal_background()


def chart_theme():
    def theme():
        f = f"{FONT}, Helvetica Neue, Arial, sans-serif"
        return {"config": {
            "font": f, "background": "transparent", "padding": 16, "autosize": {"type": "fit", "contains": "padding"},
            "view": {"stroke": None},
            "axis": {"labelColor": STONE, "titleColor": STONE, "gridColor": "rgba(211,219,207,.10)",
                     "domainColor": "rgba(211,219,207,.2)", "tickColor": "rgba(211,219,207,.2)",
                     "labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": 500, "labelFont": f, "titleFont": f},
            "legend": {"labelColor": MIST, "titleColor": STONE, "labelFont": f, "labelLimit": 260},
            "text": {"font": f},
            "range": {"category": [FERNB, LAMP, MOSSD, "#B7C9A8", STONE]},
        }}
    alt.themes.register("overgrown", theme)
    alt.themes.enable("overgrown")


# ---------------- private pages ----------------
def require_password(title: str):
    pw = cfg("DASHBOARD_PASSWORD")
    if pw and not st.session_state.get("authed"):
        st.header(title)
        st.markdown('<p class="lede">This page is private. Enter your dashboard password.</p>',
                    unsafe_allow_html=True)
        entered = st.text_input("Password", type="password")
        if entered:
            if entered == pw:
                st.session_state["authed"] = True
                st.rerun()
            st.error("That password doesn't match DASHBOARD_PASSWORD.")
        st.stop()


def private_nav():
    c = st.columns(3)
    c[0].page_link("creator.py", label="Analytics")
    c[1].page_link("calendar_page.py", label="Calendar")
    c[2].page_link("media_kit.py", label="Media kit")


# ---------------- per-reel analytics ----------------
MILESTONE_METRICS = [("views", "Views"), ("reach", "Accounts reached"), ("likes", "Likes"),
                     ("comments", "Comments"), ("shares", "Shares"), ("saved", "Saves"),
                     ("engagement", "Engagement rate"), ("avg_watch_ms", "Avg watch time")]


def milestones(snaps: pd.DataFrame, media_id: str, posted_at: pd.Timestamp) -> dict:
    """Stats at ~24 hours, ~1 week, and the latest sync, from daily snapshots."""
    s = snaps[snaps["media_id"] == media_id].sort_values("captured_date")
    if s.empty:
        return {}
    s = s.assign(age=(s["captured_date"] - posted_at.normalize()).dt.days)
    out = {}
    for key, day, slack in (("24h", 1, 1), ("week", 7, 2)):
        hit = s[s["age"] >= day]
        out[key] = hit.iloc[0] if not hit.empty and hit.iloc[0]["age"] <= day + slack else None
    out["total"] = s.iloc[-1]
    out["series"] = s
    return out


def _cell(row, key):
    if row is None:
        return '<span class="na">not captured</span>'
    if key == "engagement":
        inter = row[["likes", "comments", "shares", "saved"]].fillna(0).sum()
        tot = row["total_interactions"] if pd.notna(row["total_interactions"]) else inter
        return f"{tot / row['views']:.1%}" if row["views"] else "n/a"
    if key == "avg_watch_ms":
        return f"{row[key] / 1000:.1f}s" if pd.notna(row[key]) else "n/a"
    return fmt_num(row[key])


@st.dialog("Analytics", width="large")
def reel_dialog(media_id: str):
    media, snaps, *_ = load()
    m = media.set_index("id").loc[media_id]
    thumb = m["thumbnail_url"] if isinstance(m["thumbnail_url"], str) and m["thumbnail_url"] else None
    img = (f'<img src="{html.escape(thumb)}" alt="">' if thumb
           else '<div class="noimg"></div>')
    cap = html.escape(m["caption"] or "No caption")
    link = f'<a href="{html.escape(m["permalink"])}" target="_blank" rel="noopener">Open on Instagram</a>' \
        if isinstance(m["permalink"], str) else ""
    st.markdown(f"""<div class="reelhead">{img}<div><div class="when">{m['posted_at']:%A, %B %-d at %-I:%M %p}</div>
        <div class="cap">{cap}</div>{link}</div></div>""", unsafe_allow_html=True)

    ms = milestones(snaps, media_id, m["posted_at"])
    if not ms:
        st.info("No stats yet. They appear after the next sync.")
        return
    rows = "".join(
        f"<tr><th>{label}</th><td>{_cell(ms['24h'], k)}</td><td>{_cell(ms['week'], k)}</td>"
        f"<td>{_cell(ms['total'], k)}</td></tr>" for k, label in MILESTONE_METRICS)
    st.markdown(f"""<table class="ms"><thead><tr><th></th><th>First 24 hours</th><th>First week</th>
        <th>To date</th></tr></thead><tbody>{rows}</tbody></table>
        <p class="note">Taken from the daily sync closest to each mark. "Not captured" means the reel
        was posted before tracking began or that mark hasn’t arrived yet.</p>""", unsafe_allow_html=True)

    series = ms["series"]
    if len(series) > 1:
        line = alt.Chart(series).mark_line(point=alt.OverlayMarkDef(color=MOSS, size=40), color=MOSS, strokeWidth=2).encode(
            x=alt.X("age:Q", title="Days since posting"),
            y=alt.Y("views:Q", title="Views", axis=alt.Axis(format="~s")),
            tooltip=[alt.Tooltip("captured_date:T", title="Date"), alt.Tooltip("views:Q", format=",")],
        ).properties(height=200)
        st.altair_chart(line, width="stretch")

    st.markdown("### Portfolio")
    is_ad = st.checkbox("This is an ad or sponsored post", value=bool(m["is_ad"]), key=f"ad_{media_id}",
                        help="Ads move out of your organic stats and into the Brand partnerships section of the media kit.")
    brand = st.text_input("Brand (optional)", value=m["brand"] or "", key=f"brand_{media_id}",
                          placeholder="e.g. Nike", disabled=not is_ad)
    is_reel = db.media_kind(m["media_type"], m["product_type"]) == "reel"
    trial = st.checkbox("Posted as a trial reel", value=bool(m["is_trial"]), key=f"trial_{media_id}") if is_reel else False
    changed = (is_ad != bool(m["is_ad"]) or (is_ad and brand.strip() != (m["brand"] or ""))
               or (is_reel and trial != bool(m["is_trial"])))
    if st.button("Save", key=f"save_{media_id}", disabled=not changed, type="primary"):
        fl = flags_mod.load_flags()
        flags_mod.set_ad(fl, media_id, is_ad, brand)
        if is_reel:
            flags_mod.set_trial(fl, media_id, trial)
        ok, note = flags_mod.save_flags(fl, f"Update tags for {media_id}")
        st.cache_data.clear()
        (st.success if ok else st.warning)(note)


def show_few(df, key: str, n: int = 5):
    """First n rows unless the list has been expanded with show_few_button."""
    return df if st.session_state.get(key, False) else df.head(n)


def show_few_button(df, key: str, n: int = 5):
    """Show more / Show less toggle placed after a list cut by show_few."""
    if len(df) <= n:
        return
    is_open = st.session_state.get(key, False)
    if st.button("Show less" if is_open else f"Show {len(df) - n} more", key=key + "_btn"):
        st.session_state[key] = not is_open
        st.rerun()


def section_rail(titles: list[str]):
    """Translucent list of the page's sections that slides in when the mouse nears the left edge (PC only).
    Links go to Streamlit's built-in heading anchors."""
    slug = lambda t: re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    links = "".join(f'<a href="#{slug(t)}" target="_self">{html.escape(t)}</a>' for t in titles)
    st.markdown(f'<div class="rail-zone" aria-hidden="true"></div><nav class="rail" aria-label="Sections">{links}</nav>',
                unsafe_allow_html=True)
