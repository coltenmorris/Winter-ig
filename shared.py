"""Shared data loading, metrics, config and styling for both pages."""
import html
import os

import altair as alt
import pandas as pd
import streamlit as st

import db

LOCAL_TZ = "America/New_York"

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


# ---------------- styling (neo-Swiss) ----------------
FONT = "Schibsted Grotesk"
FONT_DISPLAY = FONT


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
.hero .id .bio {{ margin-top: 14px; max-width: 42ch; }}
.hero .avatar {{ width:44px; height:44px; border-radius:50%; object-fit:cover; order:-1; border:1px solid {RULE_C};
    display:flex; align-items:center; justify-content:center; background:{IVY}; color:{MIST}; font-weight:700; }}
.hero .count .n {{ font-size: clamp(4rem, 11vw, 9rem); font-weight: 800; line-height: .82; letter-spacing: -.06em; color: {FERNB}; }}
.hero .count .l {{ color: {STONE}; margin-top: 12px; font-weight: 500; }}
.contact {{ display:inline-block; margin-top: 22px; background: {MIST}; color: {ABYSS} !important; padding: 11px 20px;
    text-decoration: none !important; font-weight: 600; }}
.contact:hover {{ background: {LAMP}; }}

/* Stats board */
.board {{ display:grid; grid-template-columns: repeat(4, 1fr); margin-top: 44px; background: none !important;
    border: 0 !important; border-top: 1px solid {RULE_C} !important; border-bottom: 1px solid {RULE_C} !important; }}
.board > div {{ padding: 18px 20px 20px 0; min-width: 0; }}
.board > div + div {{ padding-left: 20px; border-left: 1px solid {RULE_C}; }}
.board .v {{ font-size: clamp(2rem, 4vw, 3.1rem); font-weight: 700; line-height: 1; letter-spacing: -.045em; color: {MIST}; }}
.board .k {{ color: {STONE}; font-size: .9rem; margin-top: 10px; }}
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
  .reels {{ grid-template-columns: repeat(2, minmax(0,1fr)); gap: 22px 12px; }}
  .bars .row {{ grid-template-columns: 7rem 1fr 2.8rem; }}
  .rl {{ grid-template-columns: 1fr 4.4rem 4.4rem; }}
  .rl .hide-sm {{ display:none; }}
  table.ms th, table.ms td {{ padding: 8px 3px; font-size:.82rem; }}
  table.ms td {{ font-size: .98rem; }}
}}
</style>""", unsafe_allow_html=True)


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
