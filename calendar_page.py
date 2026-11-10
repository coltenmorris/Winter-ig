"""Posting calendar: heatmap of how often you post, with a value per day. Tap a day to see its reels."""
import calendar as cal
import html
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from shared import (BARK, DUSK, FERN, MOSS, OAT, SAGE, fmt_num, load, private_nav,
                    reel_dialog, require_password, video_table)

require_password("Posting calendar")
private_nav()
st.header("Posting calendar")
st.markdown('<p class="lede">Color shows how many reels you posted each day. The number shows the value '
            'you pick below. Tap a day to see what you posted.</p>', unsafe_allow_html=True)

media, snaps, *_ = load()
t = video_table(media, snaps)
if t.empty:
    st.info("No reels yet. Run the sync first.")
    st.stop()
t = t.reset_index().rename(columns={"index": "id"})
t["date"] = t["posted_at"].dt.date

# ---------------- filters ----------------
months = pd.period_range(t["posted_at"].min().to_period("M"), pd.Timestamp.today().to_period("M"), freq="M")[::-1]
f1, f2 = st.columns(2)
month = f1.selectbox("Month", months, format_func=lambda p: p.strftime("%B %Y"))
has_views = t["views"].notna().any()
value = f2.selectbox("Number on each day", (["Views", "Engagement rate"] if has_views else [])
                     + ["Likes", "Comments"] + (["Shares"] if has_views else []) + ["Reels posted"])
with st.expander("More filters"):
    f3, f4 = st.columns(2)
    kind = f3.selectbox("Reel type", ["All reels", "Regular reels", "Trial reels"])
    all_tags = sorted({h for tags in t["hashtags"] for h in tags})
    tags = f4.multiselect("Hashtags", all_tags, placeholder="Any hashtag")

ft = t
if kind == "Regular reels":
    ft = ft[ft["is_trial"] == 0]
elif kind == "Trial reels":
    ft = ft[ft["is_trial"] == 1]
if tags:
    ft = ft[ft["hashtags"].apply(lambda hs: any(h in hs for h in tags))]

# ---------------- build the month grid ----------------
first = date(month.year, month.month, 1)
n_days = cal.monthrange(month.year, month.month)[1]
offset = first.weekday()  # Monday = 0
grid = pd.DataFrame({"date": pd.date_range(first, periods=n_days).date})
grid["dow"] = [d.strftime("%a") for d in grid["date"]]
grid["week"] = [(d.day - 1 + offset) // 7 for d in grid["date"]]
grid["day"] = [str(d.day) for d in grid["date"]]

agg = ft.groupby("date").agg(posts=("id", "size"), views=("views", "sum"), likes=("likes", "sum"),
                             comments=("comments", "sum"),
                             shares=("shares", "sum"), inter=("total_interactions", "sum")).reset_index()
grid = grid.merge(agg, on="date", how="left").fillna({"posts": 0})
grid["posts"] = grid["posts"].astype(int)
grid["level"] = grid["posts"].clip(upper=3)


def label(r):
    if r["posts"] == 0:
        return ""
    if value == "Views":
        return fmt_num(r["views"])
    if value == "Engagement rate":
        return f"{r['inter'] / r['views']:.0%}" if r["views"] else ""
    if value == "Likes":
        return fmt_num(r["likes"])
    if value == "Comments":
        return fmt_num(r["comments"])
    if value == "Shares":
        return fmt_num(r["shares"])
    return str(r["posts"])


grid["label"] = grid.apply(label, axis=1)
grid["key"] = grid["date"].astype(str)
grid["is_future"] = grid["date"] > date.today()

dows = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
pick = alt.selection_point(fields=["key"], name="day", on="click", clear=False)
base = alt.Chart(grid).encode(
    x=alt.X("dow:N", sort=dows, title=None, scale=alt.Scale(domain=dows, paddingInner=0.08),
            axis=alt.Axis(orient="top", labelAngle=0, ticks=False, domain=False, labelPadding=8)),
    y=alt.Y("week:O", title=None, axis=None, scale=alt.Scale(paddingInner=0.08)),
)
cells = base.mark_rect(cornerRadius=2, stroke="#0E1411").encode(
    color=alt.Color("level:O", scale=alt.Scale(domain=[0, 1, 2, 3], range=["#18211C", FERN, SAGE, MOSS]), legend=None),
    strokeWidth=alt.condition(pick, alt.value(1), alt.value(1)),
    opacity=alt.condition("datum.is_future", alt.value(0.45), alt.value(1)),
    tooltip=[alt.Tooltip("date:T", title="Date", format="%a %b %-d"), alt.Tooltip("posts:Q", title="Reels"),
             alt.Tooltip("views:Q", title="Views", format=",")],
).add_params(pick)
day_num = base.mark_text(dy=-11, fontSize=11).encode(
    text="day:N", color=alt.condition("datum.level >= 3", alt.value("#2A3527"), alt.value(DUSK)))
val = base.mark_text(dy=8, fontSize=15, fontWeight=500).encode(
    text="label:N", color=alt.condition("datum.level >= 3", alt.value("#0E1411"), alt.value(BARK)))
n_weeks = grid["week"].max() + 1
chart = (cells + day_num + val).properties(height=62 * n_weeks)

st.markdown(f"""<div class="cal-legend">Reels posted:
  <span><i style="background:#18211C"></i>0</span><span><i style="background:{FERN}"></i>1</span>
  <span><i style="background:{SAGE}"></i>2</span><span><i style="background:{MOSS}"></i>3+</span></div>""",
            unsafe_allow_html=True)
event = st.altair_chart(chart, width="stretch", on_select="rerun", selection_mode="day", key=f"cal_{month}")

mt = ft[(ft["posted_at"].dt.year == month.year) & (ft["posted_at"].dt.month == month.month)]
active = (grid["posts"] > 0).sum()
st.markdown(f"""<div class="summary"><span><b>{len(mt)}</b>reels this month</span>
  <span><b>{active}</b>days posted</span><span><b>{fmt_num(mt['views' if has_views else 'likes'].sum())}</b>{'views' if has_views else 'likes'} to date</span></div>""",
            unsafe_allow_html=True)

# ---------------- selected day ----------------
sel = event.selection.get("day", []) if event and hasattr(event, "selection") else []
if not sel:
    st.caption("Tap a day on the calendar to see its reels.")
    st.stop()
day = pd.to_datetime(sel[0]["key"]).date()
st.markdown(f"## {day:%A, %B %-d}")
reels = ft[ft["date"] == day].sort_values("posted_at")
if reels.empty:
    st.markdown('<p class="lede">No reels match your filters on this day.</p>', unsafe_allow_html=True)
    st.stop()

for _, r in reels.iterrows():
    thumb = r["thumbnail_url"] if isinstance(r["thumbnail_url"], str) and r["thumbnail_url"] else None
    img = f'<img src="{html.escape(thumb)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">' if thumb else '<div class="noimg"></div>'
    cap = html.escape(r["caption"] or "No caption")
    st.markdown(f"""<div class="daycard glass">{img}<div>
        <div class="when">{r['posted_at']:%-I:%M %p}{', trial reel' if r['is_trial'] else ''}</div>
        <div class="cap">{cap}</div>
        <div class="stats">{f"<b>{fmt_num(r['views'])}</b> views &nbsp; <b>{r['engagement_rate']:.1%}</b> engagement" if has_views else f"<b>{fmt_num(r['likes'])}</b> likes &nbsp; <b>{fmt_num(r['comments'])}</b> comments"}</div>
        </div></div>""", unsafe_allow_html=True)
    if st.button("View analytics", key=f"open_{r['id']}"):
        reel_dialog(r["id"])
