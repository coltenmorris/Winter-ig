"""Private analytics for deciding what to post and when."""
import altair as alt
import pandas as pd
import streamlit as st

import db
from ig_client import InstagramError
import html

from shared import (DUSK, FERN, MOSS, SAGE, SAND, fmt_num, load, private_nav, reel_dialog,
                    require_password, video_table)
from sync import run_sync

require_password("Creator analytics")
private_nav()

# ---------------- sidebar ----------------
with st.sidebar:
    window = st.selectbox("Trend window", [7, 14, 30, 90], index=0, format_func=lambda d: f"Last {d} days")
    if st.button("Sync now", width="stretch"):
        box, lines = st.empty(), []
        try:
            run_sync(log=lambda m: (lines.append(m), box.code("\n".join(lines))))
            st.cache_data.clear()
            st.success("Synced.")
        except InstagramError as e:
            st.error(f"Instagram error: {e}")
    st.caption("Instagram stats can lag up to 48 hours. On the hosted site, the daily GitHub sync is what saves history.")

media, snaps, acct, daily, demo, profile = load()
t = video_table(media, snaps, window)
st.header("Creator analytics")
if t.empty:
    st.info("No data yet. Run the sync first.")
    st.stop()

# ---------------- KPIs ----------------
cut = acct["captured_date"].max() - pd.Timedelta(days=window)
prev = acct[acct["captured_date"] <= cut]
f_now = int(acct["followers"].iloc[-1])
f_then = int(prev["followers"].iloc[-1]) if not prev.empty else int(acct["followers"].iloc[0])
c = st.columns(4)
c[0].metric("Followers", f"{f_now:,}", f"{f_now - f_then:+,}")
c[1].metric(f"Views gained, {window}d", fmt_num(t["views_gained"].sum()))
c[2].metric("Avg engagement", f"{t['engagement_rate'].mean():.1%}")
c[3].metric("Avg watch time", f"{t['avg_watch_s'].mean():.1f}s" if t["avg_watch_s"].notna().any() else "n/a")

settled = t[t["age_days"] >= 3]  # ignore reels still collecting their first views
if settled.empty:
    settled = t

# ---------------- when to post ----------------
st.markdown("## When to post")
st.markdown('<p class="lede">Median views by the day and time you posted (Eastern). '
            'Darker cells did better. Empty cells mean you haven’t posted then yet.</p>', unsafe_allow_html=True)
bucket = pd.cut(settled["posted_at"].dt.hour, [-1, 10, 14, 18, 24],
                labels=["Morning", "Midday", "Afternoon", "Evening"])
when = (settled.assign(day=settled["posted_at"].dt.day_name().str[:3], slot=bucket)
        .groupby(["day", "slot"], observed=True)["views"].agg(["median", "count"]).reset_index())
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
heat = alt.Chart(when).mark_rect(stroke="rgba(255,252,245,.9)", strokeWidth=2).encode(
    x=alt.X("day:N", sort=days, title=None, scale=alt.Scale(domain=days), axis=alt.Axis(labelAngle=0)),
    y=alt.Y("slot:N", sort=["Morning", "Midday", "Afternoon", "Evening"], title=None),
    color=alt.Color("median:Q", scale=alt.Scale(range=[FERN, MOSS]), legend=None),
    tooltip=[alt.Tooltip("day:N", title="Day"), alt.Tooltip("slot:N", title="Time"),
             alt.Tooltip("median:Q", title="Median views", format=","), alt.Tooltip("count:Q", title="Reels")],
).properties(height=220)
st.altair_chart(heat, width="stretch")

# ---------------- what works ----------------
st.markdown("## What your audience responds to")
st.markdown('<p class="lede">Average views per reel for each hashtag you’ve used at least twice, '
            'compared with your overall average (the line).</p>', unsafe_allow_html=True)
tags = settled.explode("hashtags").dropna(subset=["hashtags"])
if not tags.empty:
    tg = (tags.groupby("hashtags").agg(avg_views=("views", "mean"), reels=("views", "size"),
                                      engagement=("engagement_rate", "mean"))
          .query("reels >= 2").sort_values("avg_views", ascending=False).head(12).reset_index())
    tg["hashtags"] = "#" + tg["hashtags"]
    avg_all = settled["views"].mean()
    bars = alt.Chart(tg).mark_bar(color=SAGE).encode(
        x=alt.X("avg_views:Q", title="Average views", axis=alt.Axis(format="~s")),
        y=alt.Y("hashtags:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False, labelFontSize=13)),
        color=alt.condition(alt.datum.avg_views > avg_all, alt.value(MOSS), alt.value(SAND)),
        tooltip=["hashtags", alt.Tooltip("avg_views:Q", format=",.0f"), "reels",
                 alt.Tooltip("engagement:Q", format=".1%")],
    )
    rule = alt.Chart(pd.DataFrame({"x": [avg_all]})).mark_rule(color=DUSK, strokeDash=[4, 4]).encode(x="x:Q")
    st.altair_chart((bars + rule).properties(height=max(200, 34 * len(tg))), width="stretch")
else:
    st.caption("Add hashtags to your captions to see which topics pull the most views.")

a, b = st.columns(2, gap="large")
with a:
    st.markdown("### Hook strength")
    st.markdown('<p class="lede">Longer watch time and lower skip rate mean the first seconds are working. '
                'Top left is best.</p>', unsafe_allow_html=True)
    hook = settled.dropna(subset=["avg_watch_s", "skip_rate"]).reset_index()
    if not hook.empty:
        sc = alt.Chart(hook).mark_circle(opacity=.8, stroke="#FFFDF8", strokeWidth=1).encode(
            x=alt.X("skip_rate:Q", title="Skip rate", axis=alt.Axis(format="%")),
            y=alt.Y("avg_watch_s:Q", title="Avg watch time (s)"),
            size=alt.Size("views:Q", legend=None, scale=alt.Scale(range=[40, 600])),
            color=alt.value(MOSS),
            tooltip=["title", alt.Tooltip("views:Q", format=","), alt.Tooltip("skip_rate:Q", format=".0%"),
                     alt.Tooltip("avg_watch_s:Q", format=".1f")],
        ).properties(height=280)
        st.altair_chart(sc, width="stretch")
    else:
        st.caption("Watch time and skip rate appear for reels after a sync.")
with b:
    st.markdown("### First 48 hours")
    st.markdown('<p class="lede">How fast each recent reel picked up views. '
                'Strong early reels are the ones Instagram keeps pushing.</p>', unsafe_allow_html=True)
    s = snaps.merge(t[["posted_at", "title"]], left_on="media_id", right_index=True)
    s["day"] = (s["captured_date"] - s["posted_at"].dt.normalize()).dt.days
    early = s[s["day"].between(0, 6)]
    recent_ids = t.sort_values("posted_at").tail(4).index
    early = early[early["media_id"].isin(recent_ids)]
    if not early.empty:
        lines = alt.Chart(early).mark_line(point=True, strokeWidth=2).encode(
            x=alt.X("day:Q", title="Days since posting"),
            y=alt.Y("views:Q", title="Views", axis=alt.Axis(format="~s")),
            color=alt.Color("title:N", title=None, legend=alt.Legend(orient="bottom", columns=2, labelLimit=120)),
            tooltip=["title", "day", alt.Tooltip("views:Q", format=",")],
        ).properties(height=280)
        st.altair_chart(lines, width="stretch")

# ---------------- trial vs regular ----------------
if t["is_trial"].sum() > 0:
    st.markdown("## Trial reels vs regular reels")
    cols = st.columns(2)
    for col, (flag, name) in zip(cols, [(0, "Regular reels"), (1, "Trial reels")]):
        g = settled[settled["is_trial"] == flag]
        if g.empty:
            continue
        col.markdown(f"""<div class="glass panel"><h3 style="margin-top:0">{name}</h3>
          <div class="summary"><span><b>{len(g)}</b>reels</span><span><b>{fmt_num(g['views'].mean())}</b>avg views</span>
          <span><b>{g['engagement_rate'].mean():.1%}</b>engagement</span>
          <span><b>{g['avg_watch_s'].mean():.1f}s</b>avg watch</span></div></div>""", unsafe_allow_html=True)

# ---------------- all reels (no sideways scrolling) ----------------
st.markdown("## All reels")
st.markdown('<p class="lede">Newest first. Pick a reel to see its first 24 hours, first week and totals, '
            'or to mark it as a trial reel.</p>', unsafe_allow_html=True)
order = t.sort_values("posted_at", ascending=False)
choice = st.selectbox("Open a reel", order.index, index=None, placeholder="Choose a reel",
                      format_func=lambda i: f"{order.loc[i, 'title']} ({order.loc[i, 'posted_at']:%b %-d})")
if choice is not None:
    reel_dialog(choice)

rows = ['<div class="rl head"><span>Reel</span><span class="n">Views</span>'
        f'<span class="n">+{window}d</span><span class="n hide-sm">Engagement</span>'
        '<span class="n hide-sm">Watch</span></div>']
for i, r in order.head(60).iterrows():
    trial = '<span class="trial">Trial</span>' if r["is_trial"] else ""
    watch = f"{r['avg_watch_s']:.1f}s" if pd.notna(r["avg_watch_s"]) else ""
    rows.append(f'<div class="rl"><span class="t">{html.escape(r["title"])}{trial}'
                f'<small>{r["posted_at"]:%b %-d, %-I:%M %p}</small></span>'
                f'<span class="n">{fmt_num(r["views"])}</span><span class="n">+{fmt_num(r["views_gained"])}</span>'
                f'<span class="n hide-sm">{r["engagement_rate"]:.1%}</span><span class="n hide-sm">{watch}</span></div>')
st.markdown('<div class="glass">' + "".join(rows) + "</div>", unsafe_allow_html=True)
