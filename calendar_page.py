"""Posting calendar: what you posted each day (reels, posts or both), plus a sortable list for any date range."""
import calendar as cal
import html
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import flags as flags_mod

from shared import (BARK, DUSK, FERN, MOSS, SAGE, fmt_num, load, private_nav,
                    reel_dialog, require_password, video_table)

require_password("Posting calendar")
private_nav()
st.header("Posting calendar")
st.markdown('<p class="lede">Each day shows how many times you posted. Tap a day to list what you posted, '
            'or pick a date range below.</p>', unsafe_allow_html=True)

media, snaps, *_ = load()
t = video_table(media, snaps)
if t.empty:
    st.info("Nothing posted yet. Run the sync first.")
    st.stop()
t = flags_mod.ensure_tags(t.reset_index().rename(columns={"index": "id"}), id_col="id")
t["date"] = t["posted_at"].dt.date
has_views = t["views"].notna().any()

# ---------------- controls ----------------
c1, c2 = st.columns(2)
kind = c1.segmented_control("Show", ["Total", "Reels", "Posts"], default="Total", key="kind") or "Total"
span = c2.segmented_control("View", ["3 months", "1 month"], default="3 months", key="span") or "3 months"
ft = t if kind == "Total" else t[t["kind"] == ("reel" if kind == "Reels" else "post")]
noun = {"Total": "posts and reels", "Reels": "reels", "Posts": "posts"}[kind]

months = list(pd.period_range(t["posted_at"].min().to_period("M"), pd.Timestamp.today().to_period("M"), freq="M")[::-1])
with_posts = set(ft["posted_at"].dt.to_period("M"))
default_month = 0 if span == "3 months" else next((i for i, m in enumerate(months) if m in with_posts), 0)
end_month = st.selectbox("Ending month" if span == "3 months" else "Month", months, index=default_month, key=f"m_{span}",
                         format_func=lambda p: p.strftime("%B %Y") + ("" if p in with_posts else " (nothing posted)"))
shown = [end_month - i for i in range(3)][::-1] if span == "3 months" else [end_month]

counts = ft.groupby("date").size()
dows = ["M", "T", "W", "T ", "F", "S", "S "]  # trailing spaces keep the labels unique
today = date.today()


def month_chart(month: pd.Period):
    first = date(month.year, month.month, 1)
    n = cal.monthrange(month.year, month.month)[1]
    g = pd.DataFrame({"date": pd.date_range(first, periods=n).date})
    g["dow"] = [dows[d.weekday()] for d in g["date"]]
    g["week"] = [(d.day - 1 + first.weekday()) // 7 for d in g["date"]]
    g["posts"] = [int(counts.get(d, 0)) for d in g["date"]]
    g["level"] = g["posts"].clip(upper=3)
    g["label"] = g["posts"].map(lambda x: str(x) if x else "")
    g["key"] = g["date"].astype(str)
    pick = alt.selection_point(fields=["key"], name="day", on="click", clear=False)
    base = alt.Chart(g).encode(
        x=alt.X("dow:N", sort=dows, title=None, scale=alt.Scale(domain=dows, paddingInner=0.1),
                axis=alt.Axis(orient="top", labelAngle=0, ticks=False, domain=False, labelPadding=4, labelFontSize=10)),
        y=alt.Y("week:O", title=None, axis=None, scale=alt.Scale(paddingInner=0.1)),
    )
    cells = base.mark_rect(cornerRadius=1).encode(
        color=alt.Color("level:O", scale=alt.Scale(domain=[0, 1, 2, 3], range=["#18211C", FERN, SAGE, MOSS]), legend=None),
        opacity=alt.condition(f"datum.key > '{today}'", alt.value(0.35), alt.value(1)),
        tooltip=[alt.Tooltip("date:T", title="Date", format="%a %b %-d"), alt.Tooltip("posts:Q", title="Posted")],
    ).add_params(pick)
    num = base.mark_text(fontSize=11, fontWeight=700).encode(
        text="label:N", color=alt.condition("datum.level >= 3", alt.value("#0E1411"), alt.value(BARK)))
    weeks = g["week"].max() + 1
    return (cells + num).properties(height=26 * weeks + 22, title=alt.Title(
        month.strftime("%B %Y"), anchor="start", fontSize=13, fontWeight=600, color=BARK))


st.markdown(f"""<div class="cal-legend">Posted per day:
  <span><i style="background:#18211C"></i>0</span><span><i style="background:{FERN}"></i>1</span>
  <span><i style="background:{SAGE}"></i>2</span><span><i style="background:{MOSS}"></i>3+</span></div>""",
            unsafe_allow_html=True)
cols = st.columns(3 if span == "3 months" else [1, 1, 1])
picked = None
for col, m in zip(cols, shown):
    with col:
        ev = st.altair_chart(month_chart(m), width="stretch", on_select="rerun", selection_mode="day",
                             key=f"cal_{kind}_{m}")
        sel = ev.selection.get("day", []) if ev and hasattr(ev, "selection") else []
        if sel:
            k = sel[0]["key"]
            if st.session_state.get(f"_seen_{m}") != k:
                st.session_state[f"_seen_{m}"] = k
                picked = k

in_view = ft[ft["posted_at"].dt.to_period("M").isin(shown)]
st.markdown(f"""<div class="summary"><span><b>{len(in_view)}</b>{noun} in view</span>
  <span><b>{in_view['date'].nunique()}</b>days posted</span></div>""", unsafe_allow_html=True)

# ---------------- range + sort ----------------
PRESETS = ["Shown months", "Last 7 days", "Last 30 days", "Last 90 days", "All time", "Custom dates"]
if picked:
    day = pd.to_datetime(picked).date()
    st.session_state["preset"] = "Custom dates"
    st.session_state["custom"] = (day, day)

st.markdown(f"## {noun.capitalize()} in a range")
r1, r2 = st.columns([3, 2])
preset = r1.selectbox("Date range", PRESETS, key="preset")
sort_opts = (["Newest first", "Oldest first"] + (["Most views", "Highest engagement"] if has_views else [])
             + ["Most likes", "Most comments"])
sort = r2.selectbox("Sort by", sort_opts, key="sort")

first_shown = date(shown[0].year, shown[0].month, 1)
last_shown = date(shown[-1].year, shown[-1].month, cal.monthrange(shown[-1].year, shown[-1].month)[1])
if preset == "Shown months":
    start, end = first_shown, last_shown
    label = shown[0].strftime("%b") + (" to " + shown[-1].strftime("%b %Y") if len(shown) > 1 else " " + shown[0].strftime("%Y"))
elif preset == "Custom dates":
    if "custom" not in st.session_state:
        st.session_state["custom"] = (today - timedelta(days=30), today)
    rng = st.date_input("Dates", min_value=min(t["date"].min(), first_shown), key="custom", format="MM/DD/YYYY",
                        max_value=max(today, last_shown))
    rng = list(rng) if isinstance(rng, (tuple, list)) else [rng]
    start, end = rng[0], rng[-1]  # while picking, only the start date may be set
    label = f"{start:%b %-d}" + (f" to {end:%b %-d, %Y}" if end != start else f", {start:%Y}")
elif preset == "All time":
    start, end, label = t["date"].min(), today, "All time"
else:
    days = int(preset.split()[1])
    start, end, label = today - timedelta(days=days - 1), today, preset

rt = ft[(ft["date"] >= start) & (ft["date"] <= end)]
key, asc = {
    "Newest first": ("posted_at", False), "Oldest first": ("posted_at", True),
    "Most views": ("views", False), "Highest engagement": ("engagement_rate", False),
    "Most likes": ("likes", False), "Most comments": ("comments", False),
}[sort]
rt = rt.sort_values(key, ascending=asc, na_position="last")
main = "views" if has_views else "likes"
per = "per post" if kind != "Reels" else "per reel"
st.markdown(f"""<div class="summary"><span><b>{len(rt)}</b>{noun}, {html.escape(label)}</span>
  <span><b>{fmt_num(rt[main].sum())}</b>{main}</span>
  <span><b>{fmt_num(rt[main].mean()) if len(rt) else 0}</b>{main} {per}</span></div>""", unsafe_allow_html=True)

if rt.empty:
    st.markdown(f'<p class="lede">No {noun} in this range.</p>', unsafe_allow_html=True)
    st.stop()

for _, r in rt.iterrows():
    thumb = r["thumbnail_url"] if isinstance(r["thumbnail_url"], str) and r["thumbnail_url"] else None
    img = (f'<img src="{html.escape(thumb)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">'
           if thumb else '<div class="noimg"></div>')
    eng = f"{r['engagement_rate']:.1%}" if pd.notna(r["engagement_rate"]) else "n/a"
    stats = (f"<b>{fmt_num(r['views'])}</b> views &nbsp; <b>{eng}</b> engagement" if has_views
             else f"<b>{fmt_num(r['likes'])}</b> likes &nbsp; <b>{fmt_num(r['comments'])}</b> comments")
    what = "Reel" if r["kind"] == "reel" else ("Carousel" if r["media_type"] == "CAROUSEL_ALBUM" else "Photo")
    st.markdown(f"""<div class="daycard glass">{img}<div>
        <div class="when">{what}, {r['posted_at']:%a %b %-d, %Y at %-I:%M %p}{', trial reel' if r['is_trial'] else ''}{(', ad for ' + html.escape(r['brand']) if r['brand'] else ', ad') if r['is_ad'] else ''}</div>
        <div class="cap">{html.escape(r['caption'] or 'No caption')}</div>
        <div class="stats">{stats}</div></div></div>""", unsafe_allow_html=True)
    if st.button("View analytics", key=f"open_{r['id']}"):
        reel_dialog(r["id"])
