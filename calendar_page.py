"""Posting calendar: how many videos you posted each day, plus a sortable list for any date range."""
import calendar as cal
import html
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from shared import (BARK, DUSK, FERN, MOSS, SAGE, fmt_num, load, private_nav,
                    reel_dialog, require_password, video_table)

require_password("Posting calendar")
private_nav()
st.header("Posting calendar")
st.markdown('<p class="lede">Each day shows how many videos you posted. Tap a day to list its videos, '
            'or pick a date range below.</p>', unsafe_allow_html=True)

media, snaps, *_ = load()
t = video_table(media, snaps)
if t.empty:
    st.info("No videos yet. Run the sync first.")
    st.stop()
t = t.reset_index().rename(columns={"index": "id"})
t["date"] = t["posted_at"].dt.date
has_views = t["views"].notna().any()

# ---------------- month ----------------
months = list(pd.period_range(t["posted_at"].min().to_period("M"), pd.Timestamp.today().to_period("M"), freq="M")[::-1])
with_posts = set(t["posted_at"].dt.to_period("M"))
default_month = next((i for i, m in enumerate(months) if m in with_posts), 0)
month = st.selectbox("Month", months, index=default_month,
                     format_func=lambda p: p.strftime("%B %Y") + ("" if p in with_posts else " (no videos)"))

first = date(month.year, month.month, 1)
n_days = cal.monthrange(month.year, month.month)[1]
offset = first.weekday()  # Monday = 0
grid = pd.DataFrame({"date": pd.date_range(first, periods=n_days).date})
grid["dow"] = [d.strftime("%a") for d in grid["date"]]
grid["week"] = [(d.day - 1 + offset) // 7 for d in grid["date"]]
grid["day"] = [str(d.day) for d in grid["date"]]
counts = t.groupby("date").size().rename("posts")
grid = grid.merge(counts, left_on="date", right_index=True, how="left").fillna({"posts": 0})
grid["posts"] = grid["posts"].astype(int)
grid["level"] = grid["posts"].clip(upper=3)
grid["label"] = grid["posts"].map(lambda n: str(n) if n else "")
grid["key"] = grid["date"].astype(str)

dows = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
pick = alt.selection_point(fields=["key"], name="day", on="click", clear=False)
base = alt.Chart(grid).encode(
    x=alt.X("dow:N", sort=dows, title=None, scale=alt.Scale(domain=dows, paddingInner=0.06),
            axis=alt.Axis(orient="top", labelAngle=0, ticks=False, domain=False, labelPadding=10, labelFontSize=13)),
    y=alt.Y("week:O", title=None, axis=None, scale=alt.Scale(paddingInner=0.06)),
)
cells = base.mark_rect(stroke="#0E1411").encode(
    color=alt.Color("level:O", scale=alt.Scale(domain=[0, 1, 2, 3], range=["#18211C", FERN, SAGE, MOSS]), legend=None),
    opacity=alt.condition(f"datum.key > '{date.today()}'", alt.value(0.4), alt.value(1)),
    tooltip=[alt.Tooltip("date:T", title="Date", format="%a %b %-d"), alt.Tooltip("posts:Q", title="Videos posted")],
).add_params(pick)
day_num = base.mark_text(dy=-22, fontSize=13).encode(
    text="day:N", color=alt.condition("datum.level >= 3", alt.value("#2A3527"), alt.value(DUSK)))
val = base.mark_text(dy=10, fontSize=26, fontWeight=700).encode(
    text="label:N", color=alt.condition("datum.level >= 3", alt.value("#0E1411"), alt.value(BARK)))
n_weeks = grid["week"].max() + 1
chart = (cells + day_num + val).properties(height=96 * n_weeks)

st.markdown(f"""<div class="cal-legend">Videos posted:
  <span><i style="background:#18211C"></i>0</span><span><i style="background:{FERN}"></i>1</span>
  <span><i style="background:{SAGE}"></i>2</span><span><i style="background:{MOSS}"></i>3+</span></div>""",
            unsafe_allow_html=True)
event = st.altair_chart(chart, width="stretch", on_select="rerun", selection_mode="day", key=f"cal_{month}")

mt = t[(t["posted_at"].dt.year == month.year) & (t["posted_at"].dt.month == month.month)]
st.markdown(f"""<div class="summary"><span><b>{len(mt)}</b>videos this month</span>
  <span><b>{mt['date'].nunique()}</b>days posted</span></div>""", unsafe_allow_html=True)

# ---------------- range + sort ----------------
PRESETS = ["This month", "Last 7 days", "Last 30 days", "Last 90 days", "All time", "Custom dates"]
sel = event.selection.get("day", []) if event and hasattr(event, "selection") else []
if sel and st.session_state.get("_last_day") != sel[0]["key"]:
    # A tap on the calendar jumps the range to that day.
    day = pd.to_datetime(sel[0]["key"]).date()
    st.session_state["_last_day"] = sel[0]["key"]
    st.session_state["preset"] = "Custom dates"
    st.session_state["custom"] = (day, day)

st.markdown("## Videos in a range")
r1, r2 = st.columns([3, 2])
preset = r1.selectbox("Date range", PRESETS, key="preset")
sort_opts = (["Newest first", "Oldest first"] + (["Most views", "Highest engagement"] if has_views else [])
             + ["Most likes", "Most comments"])
sort = r2.selectbox("Sort by", sort_opts, key="sort")

today = date.today()
if preset == "This month":
    start, end = first, date(month.year, month.month, n_days)
    label = month.strftime("%B %Y")
elif preset == "Custom dates":
    if "custom" not in st.session_state:
        st.session_state["custom"] = (today - timedelta(days=30), today)
    rng = st.date_input("Dates", min_value=min(t["date"].min(), first), key="custom", format="MM/DD/YYYY",
                        max_value=max(today, date(month.year, month.month, n_days)))
    rng = list(rng) if isinstance(rng, (tuple, list)) else [rng]
    start, end = rng[0], rng[-1]  # while picking, only the start date may be set
    label = f"{start:%b %-d}" + (f" to {end:%b %-d, %Y}" if end != start else f", {start:%Y}")
elif preset == "All time":
    start, end, label = t["date"].min(), today, "All time"
else:
    days = int(preset.split()[1])
    start, end, label = today - timedelta(days=days - 1), today, preset

rt = t[(t["date"] >= start) & (t["date"] <= end)]
key, asc = {
    "Newest first": ("posted_at", False), "Oldest first": ("posted_at", True),
    "Most views": ("views", False), "Highest engagement": ("engagement_rate", False),
    "Most likes": ("likes", False), "Most comments": ("comments", False),
}[sort]
rt = rt.sort_values(key, ascending=asc, na_position="last")
main = "views" if has_views else "likes"
st.markdown(f"""<div class="summary"><span><b>{len(rt)}</b>videos, {html.escape(label)}</span>
  <span><b>{fmt_num(rt[main].sum())}</b>{main}</span>
  <span><b>{fmt_num(rt[main].mean()) if len(rt) else 0}</b>{main} per video</span></div>""", unsafe_allow_html=True)

if rt.empty:
    st.markdown('<p class="lede">No videos posted in this range.</p>', unsafe_allow_html=True)
    st.stop()

for _, r in rt.iterrows():
    thumb = r["thumbnail_url"] if isinstance(r["thumbnail_url"], str) and r["thumbnail_url"] else None
    img = (f'<img src="{html.escape(thumb)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">'
           if thumb else '<div class="noimg"></div>')
    stats = (f"<b>{fmt_num(r['views'])}</b> views &nbsp; <b>{r['engagement_rate']:.1%}</b> engagement" if has_views
             else f"<b>{fmt_num(r['likes'])}</b> likes &nbsp; <b>{fmt_num(r['comments'])}</b> comments")
    st.markdown(f"""<div class="daycard glass">{img}<div>
        <div class="when">{r['posted_at']:%a, %b %-d, %Y at %-I:%M %p}{', trial reel' if r['is_trial'] else ''}</div>
        <div class="cap">{html.escape(r['caption'] or 'No caption')}</div>
        <div class="stats">{stats}</div></div></div>""", unsafe_allow_html=True)
    if st.button("View analytics", key=f"open_{r['id']}"):
        reel_dialog(r["id"])
