"""Private analytics for deciding what to post and when."""
import altair as alt
import pandas as pd
import streamlit as st

import db
import flags as flags_mod
from ig_client import InstagramError
import html

from shared import (section_rail, show_few, show_few_button, DUSK, FERN, MOSS, SAGE, SAND, fmt_num, load, private_nav, reel_dialog,
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
t = flags_mod.ensure_tags(video_table(media, snaps, window))
t = t[t["kind"] == "reel"] if not t.empty else t  # analytics are reels only; the calendar covers posts too
st.caption("Tip: open any reel and use Portfolio to tag it as an ad. Ads leave your organic stats on the media kit "
           "and appear under Brand partnerships.")
st.header("Creator analytics")
from live import live_followers  # noqa: E402
live_followers(int(acct["followers"].iloc[-1]) if not acct.empty else None)
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

# ---------------- period summary ----------------
_rail_extra = []
st.markdown("## Summary by period")
st.markdown('<p class="lede">Videos grouped by when you posted them, with their views, likes and engagement to date. '
            'Followers come from the daily sync, so periods before tracking started show a dash.</p>',
            unsafe_allow_html=True)
gran = st.segmented_control("Breakdown", ["Monthly", "Weekly", "Daily"], default="Monthly", key="gran") or "Monthly"
freq = {"Monthly": "M", "Weekly": "W-SUN", "Daily": "D"}[gran]
has_views_p = t["views"].notna().any()
pt = t.assign(period=t["posted_at"].dt.to_period(freq))
summ = pt.groupby("period").agg(videos=("views", "size"), views=("views", "sum"), likes=("likes", "sum"),
                                inter=("total_interactions", "sum"))
summ["eng"] = summ["inter"] / summ["views"].where(summ["views"] > 0)
fol = acct.assign(period=acct["captured_date"].dt.to_period(freq)).groupby("period")["followers"].last()
summ = summ.join(fol.rename("followers"), how="outer").sort_index(ascending=False)
summ["fchange"] = summ["followers"] - summ["followers"].shift(-1)
summ = summ.head({"Monthly": 24, "Weekly": 26, "Daily": 45}[gran])


def plabel(p):
    if gran == "Monthly":
        return p.strftime("%b %Y")
    if gran == "Weekly":
        return "Week of " + p.start_time.strftime("%b %-d, %Y")
    return p.start_time.strftime("%a, %b %-d, %Y")


main_col = "views" if has_views_p else "likes"
short_lbl = (lambda p: p.strftime("%b %y")) if gran == "Monthly" else (lambda p: p.start_time.strftime("%b %-d '%y"))
chart_df = summ.reset_index().assign(label=lambda d: d["period"].map(short_lbl)).iloc[::-1]
bars = alt.Chart(chart_df.dropna(subset=["videos"])).mark_bar(color=SAGE).encode(
    x=alt.X("label:N", sort=None, title=None,
            axis=alt.Axis(labelAngle=0 if len(chart_df) <= 6 else -45, labelLimit=110, labelOverlap=False, labelFontSize=11)),
    y=alt.Y(f"{main_col}:Q", title=main_col.capitalize(), axis=alt.Axis(format="~s")),
    tooltip=[alt.Tooltip("label:N", title="Period"), alt.Tooltip(f"{main_col}:Q", format=","),
             alt.Tooltip("videos:Q", title="Videos")],
).properties(height=220)
st.altair_chart(bars, width="stretch")

dash = '<span class="na">-</span>'
rows = ['<div class="ps head"><span>Period</span><span class="n hide-sm">Videos</span><span class="n">Views</span>'
        '<span class="n hide-sm">Likes</span><span class="n">Engagement</span><span class="n">Followers</span></div>']
for p, r in summ.iterrows():
    eng_txt = f"{r['eng']:.1%}" if pd.notna(r["eng"]) else dash
    fc = "" if pd.isna(r["fchange"]) or r["fchange"] == 0 else f'<small>{r["fchange"]:+,.0f}</small>'
    rows.append(
        f'<div class="ps"><span>{plabel(p)}</span>'
        f'<span class="n hide-sm">{int(r["videos"]) if pd.notna(r["videos"]) else 0}</span>'
        f'<span class="n">{fmt_num(r["views"]) if has_views_p and pd.notna(r["views"]) else dash}</span>'
        f'<span class="n hide-sm">{fmt_num(r["likes"]) if pd.notna(r["likes"]) else dash}</span>'
        f'<span class="n">{eng_txt}</span>'
        f'<span class="n">{fmt_num(r["followers"]) if pd.notna(r["followers"]) else dash}{fc}</span></div>')
st.markdown('<div class="glass">' + "".join(rows) + "</div>", unsafe_allow_html=True)

# ---------------- stories ----------------
st.markdown("## Stories")
_sc = db.connect()
stories = pd.read_sql_query("""SELECT s.*, st.* FROM stories s LEFT JOIN story_stats st ON st.story_id = s.id""", _sc)
_sc.close()
if stories.empty:
    st.markdown('<p class="lede">No stories saved yet. Each story\'s stats are saved every hour while it\'s live. '
                "Instagram deletes story stats 24 hours after posting, so stories from before this started can't be added.</p>",
                unsafe_allow_html=True)
else:
    stories["posted_at"] = (pd.to_datetime(stories["posted_at"], utc=True).dt.tz_convert("America/Los_Angeles")
                            .dt.tz_localize(None))
    stories = stories.sort_values("posted_at")
    stories["sv"] = stories["views"].fillna(stories["reach"])
    age = (pd.Timestamp.now(tz="America/Los_Angeles").tz_localize(None) - stories["posted_at"]).dt.total_seconds() / 86400
    pool, s_lbl = (stories[age <= 30], "last 30 days") if (age <= 30).any() else (stories, "all time")
    ex = pool.dropna(subset=["exits"])
    ex = ex[ex["sv"] > 0]
    exit_rate = ex["exits"].sum() / ex["sv"].sum() if not ex.empty else None
    follows = int(pool["follows"].fillna(0).sum())
    n = len(pool)
    st.markdown(f'<p class="lede">{n} {"story" if n == 1 else "stories"} posted, {s_lbl}.'
                + (f' {follows:,} new follow{"" if follows == 1 else "s"} came from stories.' if follows else "")
                + " Numbers are saved every hour, so each story keeps its last count before Instagram expires it after 24 hours.</p>",
                unsafe_allow_html=True)
    st.markdown(f"""<div class="board four glass">
      <div><div class="v">{fmt_num(pool["sv"].mean())}</div><div class="k">Avg views per story</div></div>
      <div><div class="v">{fmt_num(pool["reach"].mean())}</div><div class="k">Avg accounts reached</div></div>
      <div><div class="v">{f"{exit_rate:.1%}" if exit_rate is not None else "n/a"}</div><div class="k">Exit rate (left your stories)</div></div>
      <div><div class="v">{fmt_num(pool["replies"].sum()) if pool["replies"].notna().any() else "n/a"}</div><div class="k">Replies</div></div>
    </div>""", unsafe_allow_html=True)

    def s_card(r):
        img = (f'<img src="{html.escape(r["thumbnail_url"])}" alt="" loading="lazy" referrerpolicy="no-referrer" '
               f'onerror="this.remove()">' if isinstance(r["thumbnail_url"], str) else "")
        return (f'<div class="scard"><div class="sthumb">{img}</div>'
                f'<div class="st-t">{r["posted_at"]:%-I:%M %p}</div>'
                f'<div class="st-v">{fmt_num(r["sv"])} <span>{"views" if pd.notna(r["views"]) else "reached"}</span></div>'
                f'<dl><dt>Reach</dt><dd>{fmt_num(r["reach"])}</dd><dt>Replies</dt><dd>{fmt_num(r["replies"])}</dd>'
                f'<dt>Forward taps</dt><dd>{fmt_num(r["taps_forward"])}</dd><dt>Exits</dt><dd>{fmt_num(r["exits"])}</dd></dl></div>')

    by_day = list(stories.groupby(stories["posted_at"].dt.date))[::-1]
    show_all = st.session_state.get("st_all", False)
    blocks = []
    for d, g in (by_day if show_all else by_day[:7]):
        first, last = g["sv"].iloc[0], g["sv"].iloc[-1]
        hold = (f" {last / first:.1%} of first-story viewers stayed to the last."
                if len(g) > 1 and pd.notna(first) and first and pd.notna(last) else "")
        blocks.append(f'<div class="sday"><div class="sday-h"><b>{d:%a, %b %-d}</b><span>{len(g)} '
                      f'{"story" if len(g) == 1 else "stories"}.{hold}</span></div>'
                      f'<div class="sgrid">{"".join(s_card(r) for _, r in g.iterrows())}</div></div>')
    st.markdown("".join(blocks), unsafe_allow_html=True)
    if len(by_day) > 7 and not show_all:
        if st.button(f"Show {len(by_day) - 7} earlier days"):
            st.session_state["st_all"] = True
            st.rerun()

# ---------------- when to post ----------------
st.markdown("## When to post")
st.markdown('<p class="lede">Median views by the day and time you posted (Pacific time). '
            'Darker cells did better. Empty cells mean you haven’t posted then yet.</p>', unsafe_allow_html=True)
SLOTS = ["Late night", "Morning", "Midday", "Afternoon", "Evening"]  # 12–5a, 5–11a, 11a–3p, 3–7p, 7p–12a
bucket = pd.cut(settled["posted_at"].dt.hour, [-1, 4, 10, 14, 18, 23], labels=SLOTS)
when = (settled.assign(day=settled["posted_at"].dt.day_name().str[:3], slot=bucket.astype(str))
        .groupby(["day", "slot"], observed=True)["views"].agg(["median", "count"]).reset_index())
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
heat = alt.Chart(when).mark_rect(stroke="#0E1411", strokeWidth=2).encode(
    x=alt.X("day:N", sort=days, title=None, scale=alt.Scale(domain=days), axis=alt.Axis(labelAngle=0)),
    y=alt.Y("slot:N", sort=SLOTS, title=None, scale=alt.Scale(domain=SLOTS)),
    color=alt.Color("median:Q", scale=alt.Scale(range=[FERN, MOSS]), legend=None),
    tooltip=[alt.Tooltip("day:N", title="Day"), alt.Tooltip("slot:N", title="Time"),
             alt.Tooltip("median:Q", title="Median views", format=","), alt.Tooltip("count:Q", title="Reels")],
).properties(height=270)
st.altair_chart(heat, width="stretch")

# ---------------- what works ----------------
st.markdown("## What your audience responds to")
st.markdown('<p class="lede">Your top 3 hashtags by average views per reel (used at least twice), '
            'compared with your overall average (the line).</p>', unsafe_allow_html=True)
tags = settled.explode("hashtags").dropna(subset=["hashtags"])
if not tags.empty:
    tg = (tags.groupby("hashtags").agg(avg_views=("views", "mean"), reels=("views", "size"),
                                      engagement=("engagement_rate", "mean"))
          .query("reels >= 2").sort_values("avg_views", ascending=False).reset_index())
    tg["hashtags"] = "#" + tg["hashtags"]
    avg_all = settled["views"].mean()
    xmax = tg["avg_views"].max() * 1.05 if not tg.empty else 1

    def tag_chart(df):
        bars = alt.Chart(df).mark_bar(color=SAGE).encode(
            x=alt.X("avg_views:Q", title="Average views", axis=alt.Axis(format="~s"), scale=alt.Scale(domain=[0, xmax])),
            y=alt.Y("hashtags:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False, labelFontSize=13)),
            color=alt.condition(alt.datum.avg_views > avg_all, alt.value(MOSS), alt.value(SAGE)),
            tooltip=["hashtags", alt.Tooltip("avg_views:Q", format=",.0f"), "reels",
                     alt.Tooltip("engagement:Q", format=".1%")],
        )
        rule = alt.Chart(pd.DataFrame({"x": [avg_all]})).mark_rule(color=DUSK, strokeDash=[4, 4]).encode(x="x:Q")
        return (bars + rule).properties(height=max(120, 38 * len(df)))

    st.altair_chart(tag_chart(tg.head(3)), width="stretch")
    if len(tg) > 3:
        with st.expander(f"Show all {len(tg)} hashtags"):
            st.altair_chart(tag_chart(tg.iloc[3:]), width="stretch")
else:
    st.caption("Add hashtags to your captions to see which topics pull the most views.")

a, b = st.columns(2, gap="large")
with a:
    st.markdown("### Hook strength")
    st.markdown('<p class="lede">Longer watch time and lower skip rate mean the first seconds are working. '
                'Top left is best.</p>', unsafe_allow_html=True)
    hook = settled.dropna(subset=["avg_watch_s", "skip_rate"]).reset_index()
    if not hook.empty:
        sc = alt.Chart(hook).mark_circle(opacity=.8, stroke="#0E1411", strokeWidth=1).encode(
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
    _rail_extra.append("Trial reels vs regular reels")
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
for i, r in show_few(order, "reels_open", 10).iterrows():
    trial = ('<span class="trial">Trial</span>' if r["is_trial"] else "") + \
        (f'<span class="trial">Ad{": " + html.escape(r["brand"]) if r["brand"] else ""}</span>' if r["is_ad"] else "")
    watch = f"{r['avg_watch_s']:.1f}s" if pd.notna(r["avg_watch_s"]) else ""
    rows.append(f'<div class="rl"><span class="t">{html.escape(r["title"])}{trial}'
                f'<small>{r["posted_at"]:%b %-d, %-I:%M %p}</small></span>'
                f'<span class="n">{fmt_num(r["views"])}</span><span class="n">+{fmt_num(r["views_gained"])}</span>'
                f'<span class="n hide-sm">{r["engagement_rate"]:.1%}</span><span class="n hide-sm">{watch}</span></div>')
st.markdown('<div class="glass">' + "".join(rows) + "</div>", unsafe_allow_html=True)
show_few_button(order, "reels_open", 10)
section_rail(["Summary by period", "Stories", "When to post", "What your audience responds to"]
             + (["Trial reels vs regular reels"] if "Trial reels vs regular reels" in _rail_extra else []) + ["All reels"])
