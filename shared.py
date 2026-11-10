"""Shared data loading, metrics, config and styling for both pages."""
import html
import os

import altair as alt
import pandas as pd
import streamlit as st

import db

LOCAL_TZ = "America/New_York"

# ---------------- palette (muted Hyperbloom: sage, moss, tan) ----------------
MOSS = "#4F5D43"     # deep green: headings, primary data
SAGE = "#8E9F7E"     # mid green: secondary data
FERN = "#C9D2B8"     # pale green: fills, tracks
SAND = "#CDB592"     # tan: highlights, best performers
OAT = "#EFE7D8"      # light base
BARK = "#4A3F33"     # body text
DUSK = "#7C7062"     # secondary text
LINE = "rgba(255,252,245,.75)"  # hairlines
GLASS = "rgba(250,246,238,.5)"  # translucent panels
# aliases used by the pages
NAVY, LANE, SPLIT, RULE, SLATE, INK, CHALK = MOSS, SAGE, SAND, FERN, DUSK, BARK, OAT


def cfg(key: str, default: str = "") -> str:
    """Read a setting from Streamlit secrets, then environment variables."""
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


# ---------------- data ----------------
@st.cache_data(ttl=300)
def load():
    conn = db.connect()
    q = lambda sql: pd.read_sql(sql, conn)
    media, snaps = q("SELECT * FROM media"), q("SELECT * FROM media_snapshots")
    acct = q("SELECT * FROM account_snapshots ORDER BY captured_date")
    daily = q("SELECT * FROM account_daily ORDER BY captured_date")
    demo = q("SELECT * FROM demographics")
    profile = {k.replace("profile_", ""): v for k, v in
               conn.execute("SELECT key, value FROM settings WHERE key LIKE 'profile_%'").fetchall()}
    conn.close()
    for df in (snaps, acct, daily):
        df["captured_date"] = pd.to_datetime(df["captured_date"])
    media["posted_at"] = pd.to_datetime(media["posted_at"], utc=True).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    return media, snaps, acct, daily, demo, profile


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
    t["hashtags"] = t["caption"].fillna("").str.findall(r"#(\w+)").apply(lambda x: [h.lower() for h in x])
    t["age_days"] = (pd.Timestamp.now() - t["posted_at"]).dt.days
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


# ---------------- styling ----------------
FONT = "Jost"
FONT_DISPLAY = "Italiana"
FONT_SCRIPT = "Pinyon Script"


def inject_css():
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Italiana&family=Jost:wght@300;400;500&family=Pinyon+Script&display=swap');
html, body, [class*="st-"], .stMarkdown, button, input, textarea {{ font-family: '{FONT}', system-ui, sans-serif; }}

/* The bloom: soft blurred color field behind everything */
.stApp {{ background: {OAT}; color: {BARK}; }}
.stApp::before {{ content:""; position:fixed; inset:-14vmax; z-index:0; pointer-events:none; filter: blur(60px) saturate(1.05);
  background:
    radial-gradient(34vmax 28vmax at 10% 14%, #8A9C78 0%, transparent 68%),
    radial-gradient(36vmax 30vmax at 82% 8%, #CDAE82 0%, transparent 68%),
    radial-gradient(30vmax 34vmax at 58% 52%, #B9C6A2 0%, transparent 70%),
    radial-gradient(30vmax 26vmax at 14% 80%, #C2A57C 0%, transparent 68%),
    radial-gradient(28vmax 26vmax at 94% 82%, #6E8160 0%, transparent 68%),
    radial-gradient(22vmax 18vmax at 40% 96%, #9DAA84 0%, transparent 70%); }}
/* Hairline frame inset from the viewport edge */
.stApp::after {{ content:""; position:fixed; inset:14px; border:1px solid {LINE}; z-index:0; pointer-events:none; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: rgba(239,231,216,.7); backdrop-filter: blur(14px); border-right:1px solid {LINE}; }}
.block-container {{ max-width: 1080px; padding-top: 3rem; padding-bottom: 4rem; position:relative; z-index:1; }}

h1, h2, h3 {{ font-family: '{FONT_DISPLAY}', serif !important; color: {MOSS}; font-weight: 400 !important; }}
h2 {{ font-size: 2.6rem !important; letter-spacing: .04em; margin: 3rem 0 .1rem !important; }}
h3 {{ font-size: 1.35rem !important; letter-spacing: .03em; }}
.lede {{ color: {DUSK}; font-weight: 300; font-size: 1.02rem; margin: 0 0 1.2rem; max-width: 62ch; }}
a {{ color: {MOSS}; }}
:focus-visible {{ outline: 2px solid {MOSS} !important; outline-offset: 3px; }}

.glass {{ background: {GLASS}; backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid {LINE}; }}
.stripes {{ height: 34px; background: repeating-linear-gradient(to bottom, {LINE} 0 2px, transparent 2px 7px); }}
.stripes.short {{ width: 120px; height: 22px; }}

/* Hero */
.hero {{ display:grid; grid-template-columns: 1fr 1.35fr; gap: 0; position: relative; }}
.hero .count {{ padding: 28px 30px; border:1px solid {LINE}; border-right:none; position:relative; overflow:hidden; }}
.hero .count .n {{ font: 400 6.4rem/0.9 '{FONT_DISPLAY}'; color: {MOSS}; letter-spacing: .01em; }}
.hero .count .l {{ font-weight: 300; color: {DUSK}; margin-top: 8px; letter-spacing:.04em; }}
.hero .count .px {{ position:absolute; right:22px; top:22px; width:64px; height:40px; opacity:.6;
    background: conic-gradient({LINE} 25%, transparent 0 50%, {LINE} 0 75%, transparent 0) 0 0/10px 10px; }}
.hero .id {{ padding: 26px 30px 24px; }}
.hero .id h1 {{ font-size: 3.6rem !important; line-height: 1 !important; letter-spacing: .05em; margin:0 !important; padding:0 !important; }}
.hero .id .row {{ display:flex; justify-content:space-between; align-items:center; gap: 16px; margin-top: 16px; }}
.hero .id .handle {{ font-weight:300; color: {DUSK}; letter-spacing:.05em; }}
.hero .id .bio {{ font-weight:300; color: {BARK}; margin-top: 12px; max-width: 46ch; line-height: 1.5; }}
.hero .avatar {{ width:64px; height:64px; border-radius:50%; object-fit:cover; border:1px solid {LINE};
    display:flex; align-items:center; justify-content:center; background:{FERN}; color:{MOSS}; font: 400 1.8rem '{FONT_DISPLAY}'; }}
.script {{ font-family: '{FONT_SCRIPT}', cursive; color: {MOSS}; font-size: 4.4rem; line-height: 1; margin: 6px 0 -6px 30px; }}
.contact {{ display:inline-block; margin-top: 16px; border:1px solid {MOSS}; color: {MOSS} !important; font-weight: 400;
    padding: 8px 18px; text-decoration: none !important; letter-spacing:.04em; background: rgba(255,252,245,.35); }}
.contact:hover {{ background: {MOSS}; color: {OAT} !important; }}

/* Stats board */
.board {{ display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 18px; }}
.board > div {{ padding: 18px 22px; border-left: 1px solid {LINE}; }}
.board > div:first-child {{ border-left: none; }}
.board .v {{ font: 400 2.9rem/1 '{FONT_DISPLAY}'; color: {MOSS}; }}
.board .k {{ color: {DUSK}; font-weight: 300; font-size: .95rem; margin-top: 8px; }}
.board .d {{ color: {MOSS}; font-size: .85rem; margin-top: 2px; }}

/* Reel cards */
.reels {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }}
.reel {{ text-decoration:none !important; color:{BARK} !important; display:block; }}
.reel .thumb {{ aspect-ratio: 4/5; position: relative; overflow:hidden; border:1px solid {LINE};
    background: radial-gradient(60% 50% at 30% 30%, {SAND}, transparent 70%),
                radial-gradient(70% 60% at 75% 70%, {SAGE}, transparent 70%), {FERN}; }}
.reel .thumb img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.reel .thumb .ph {{ position:absolute; inset:auto 16px 16px 16px; color:#FFFDF8; font: 400 1.55rem/1.1 '{FONT_DISPLAY}'; letter-spacing:.03em; }}
.reel .best {{ position:absolute; top:12px; left:12px; border:1px solid #FFFDF8; color:#FFFDF8; font-weight:400;
    font-size:.8rem; padding:3px 9px; letter-spacing:.05em; background: rgba(79,93,67,.35); backdrop-filter: blur(6px); }}
.reel .meta {{ display:flex; justify-content: space-between; padding: 12px 14px 4px; }}
.reel .meta b {{ font: 400 1.8rem/1 '{FONT_DISPLAY}'; color:{MOSS}; display:block; }}
.reel .meta span {{ color:{DUSK}; font-weight:300; font-size:.85rem; }}
.reel .t {{ padding: 4px 14px 14px; color:{DUSK}; font-weight:300; font-size:.92rem; line-height:1.35; }}
.reel .card {{ border:1px solid {LINE}; border-top:none; }}

/* Audience bars */
.panel {{ padding: 18px 22px 20px; }}
.bars .row {{ display:grid; grid-template-columns: 10rem 1fr 3.2rem; gap: 12px; align-items:center; margin: 9px 0; }}
.bars .lbl {{ font-size:.95rem; font-weight: 300; }}
.bars .track {{ height: 6px; background: rgba(255,252,245,.6); overflow:hidden; }}
.bars .fill {{ height:100%; background: linear-gradient(90deg, {SAGE}, {MOSS}); }}
.bars .pct {{ text-align:right; color:{DUSK}; font-variant-numeric: tabular-nums; font-size:.92rem; }}
.split {{ display:flex; height: 8px; overflow:hidden; margin: 12px 0 10px; }}
.legend {{ color:{DUSK}; font-weight:300; font-size:.92rem; }}
.legend i {{ display:inline-block; width:10px; height:10px; margin-right:6px; vertical-align:-1px; }}

.foot {{ color:{DUSK}; font-weight:300; font-size:.88rem; margin-top: 3.5rem; padding-top: 12px; border-top:1px solid {LINE}; }}
[data-testid="stMetricValue"] {{ font-family:'{FONT_DISPLAY}'; color:{MOSS}; font-size: 2.4rem; }}
[data-testid="stMetric"] {{ background:{GLASS}; border:1px solid {LINE}; padding: 14px 18px; backdrop-filter: blur(14px); }}
[data-testid="stVegaLiteChart"], [data-testid="stDataFrame"] {{ box-sizing: border-box; overflow: hidden; background:{GLASS}; border:1px solid {LINE}; padding:0; backdrop-filter: blur(14px); }}
.stButton > button {{ border-radius: 0; border:1px solid {MOSS}; }}

/* No sideways scrolling anywhere */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ overflow-x: hidden; max-width: 100vw; }}
img {{ max-width: 100%; }}

/* Reel pop-up */
.reelhead {{ display:grid; grid-template-columns: 96px 1fr; gap: 16px; align-items:start; margin-bottom: 14px; }}
.reelhead img, .reelhead .noimg {{ width:96px; aspect-ratio: 4/5; object-fit:cover; border:1px solid {LINE};
    background: radial-gradient(60% 50% at 30% 30%, {SAND}, transparent 70%), radial-gradient(70% 60% at 75% 70%, {SAGE}, transparent 70%), {FERN}; }}
.reelhead .when {{ color:{DUSK}; font-size:.9rem; }}
.reelhead .cap {{ margin: 6px 0 8px; line-height:1.45; overflow-wrap:anywhere; }}
table.ms {{ width:100%; border-collapse: collapse; table-layout: fixed; font-variant-numeric: tabular-nums; }}
table.ms th, table.ms td {{ padding: 8px 6px; border-bottom: 1px solid {FERN}; text-align:right; font-size:.95rem; }}
table.ms thead th {{ color:{DUSK}; font-weight:400; font-size:.85rem; vertical-align:bottom; }}
table.ms tbody th {{ text-align:left; font-weight:400; color:{BARK}; }}
table.ms th:first-child {{ width: 34%; }}
table.ms td {{ font-family:'{FONT_DISPLAY}', serif; font-size: 1.2rem; color:{MOSS}; }}
table.ms .na {{ font-family:'{FONT}', sans-serif; font-size:.78rem; color:{DUSK}; }}
.note {{ color:{DUSK}; font-size:.82rem; margin-top:8px; }}

/* Calendar day list */
.daycard {{ display:grid; grid-template-columns: 84px 1fr; gap: 14px; padding: 12px; margin-bottom: 4px; }}
.daycard img, .daycard .noimg {{ width:84px; aspect-ratio:4/5; object-fit:cover; border:1px solid {LINE};
    background: radial-gradient(60% 50% at 30% 30%, {SAND}, transparent 70%), radial-gradient(70% 60% at 75% 70%, {SAGE}, transparent 70%), {FERN}; }}
.daycard .when {{ color:{DUSK}; font-size:.85rem; }}
.daycard .cap {{ margin-top: 4px; line-height:1.4; overflow-wrap:anywhere; }}
.daycard .stats {{ margin-top: 8px; color:{DUSK}; font-size:.88rem; }}
.daycard .stats b {{ color:{MOSS}; font-weight:500; }}
.cal-legend {{ display:flex; gap: 14px; align-items:center; color:{DUSK}; font-size:.88rem; flex-wrap: wrap; margin: 4px 0 10px; }}
.cal-legend i {{ display:inline-block; width:14px; height:14px; margin-right:6px; vertical-align:-2px; border:1px solid {LINE}; }}
.summary {{ display:flex; flex-wrap:wrap; gap: 8px 28px; color:{DUSK}; margin: 2px 0 14px; }}
.summary b {{ font-family:'{FONT_DISPLAY}', serif; font-size:1.5rem; color:{MOSS}; font-weight:400; margin-right:6px; }}

/* Reel list (replaces the wide table) */
.rl {{ display:grid; grid-template-columns: 1fr repeat(4, 5.2rem); gap: 0 10px; align-items:center;
       padding: 10px 14px; border-bottom: 1px solid {LINE}; font-variant-numeric: tabular-nums; }}
.rl.head {{ color:{DUSK}; font-size:.85rem; }}
.rl .t {{ overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }}
.rl .t small {{ color:{DUSK}; display:block; }}
.rl .n {{ text-align:right; }}
.rl .trial {{ font-size:.75rem; border:1px solid {SAND}; color:{BARK}; padding:1px 6px; margin-left:6px; }}

@media (max-width: 760px) {{
  .rl {{ grid-template-columns: 1fr 4.4rem 4.4rem; }}
  .rl .hide-sm {{ display:none; }}
  table.ms th, table.ms td {{ padding: 7px 3px; font-size:.85rem; }}
  table.ms td {{ font-size: 1.02rem; }}
  .stApp::after {{ inset: 8px; }}
  .hero {{ grid-template-columns: 1fr; }}
  .hero .count {{ border-right:1px solid {LINE}; border-bottom:none; }}
  .hero .count .n {{ font-size: 4.6rem; }}
  .hero .id h1 {{ font-size: 2.6rem !important; }}
  .script {{ font-size: 3.2rem; margin-left: 10px; }}
  .board {{ grid-template-columns: repeat(2, 1fr); }}
  .board > div:nth-child(3) {{ border-left:none; }}
  .board > div:nth-child(n+3) {{ border-top: 1px solid {LINE}; }}
  .reels {{ grid-template-columns: repeat(2, 1fr); gap: 12px; }}
  .bars .row {{ grid-template-columns: 7.5rem 1fr 2.8rem; }}
}}
@media (prefers-reduced-transparency: reduce) {{ .glass {{ background: rgba(239,231,216,.95); }} }}
</style>""", unsafe_allow_html=True)


def chart_theme():
    def theme():
        return {"config": {
            "font": f"{FONT}, Helvetica, Arial, sans-serif", "background": "transparent", "padding": 16, "autosize": {"type": "fit", "contains": "padding"},
            "view": {"stroke": None},
            "axis": {"labelColor": DUSK, "titleColor": DUSK, "gridColor": "rgba(255,252,245,.8)",
                     "domainColor": "rgba(255,252,245,.9)", "tickColor": "rgba(255,252,245,.9)",
                     "labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": 400, "labelFont": f"{FONT}, Helvetica, sans-serif", "titleFont": f"{FONT}, Helvetica, sans-serif"},
            "legend": {"labelColor": BARK, "titleColor": DUSK, "labelFont": f"{FONT}, Helvetica, sans-serif", "labelLimit": 260},
            "range": {"category": [MOSS, SAND, SAGE, "#A68B66", FERN]},
        }}
    alt.themes.register("bloom", theme)
    alt.themes.enable("bloom")


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


@st.dialog("Reel analytics", width="large")
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

    trial = st.checkbox("Posted as a trial reel", value=bool(m["is_trial"]), key=f"trial_{media_id}")
    if trial != bool(m["is_trial"]):
        conn = db.connect()
        db.set_trial(conn, media_id, trial)
        conn.close()
        st.cache_data.clear()
