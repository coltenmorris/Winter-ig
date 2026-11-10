"""Partner-facing media kit."""
import html
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from shared import LANE, MOSS, SAGE, NAVY, SAND, SPLIT, RULE, cfg, fmt_num, load, video_table

media, snaps, acct, daily, demo, profile = load()
t = video_table(media, snaps, window_days=30)

if t.empty or acct.empty:
    st.header("Media kit")
    st.write("Stats will appear here after the first sync.")
    st.stop()

esc = html.escape
name = cfg("CREATOR_NAME") or profile.get("name") or profile.get("username", "")
handle = profile.get("username") or acct["username"].dropna().iloc[-1]
bio = cfg("CREATOR_TAGLINE") or profile.get("biography", "")
email = cfg("CONTACT_EMAIL")
pic = profile.get("profile_picture_url")

# ---------------- headline numbers ----------------
now = acct["captured_date"].max()
followers = int(acct["followers"].iloc[-1])
past = acct[acct["captured_date"] <= now - pd.Timedelta(days=30)]
base = int(past["followers"].iloc[-1]) if not past.empty else int(acct["followers"].iloc[0])
gained = followers - base
growth_pct = gained / base if base else 0

recent = t[(t["age_days"] <= 90) & (t["age_days"] >= 3)]
if len(recent) < 3:
    recent = t
HAS_VIEWS = t["views"].notna().any()
MAIN, MAIN_L = ("views", "views") if HAS_VIEWS else ("likes", "likes")
avg_views = recent[MAIN].mean()
eng = recent["engagement_rate"].mean() if HAS_VIEWS else None

d30 = daily[daily["captured_date"] > now - pd.Timedelta(days=30)]
views_30 = d30["views"].sum() if d30["views"].notna().any() else t[MAIN].sum()
v30_label = "Views in the last 30 days" if d30["views"].notna().any() else f"Total {MAIN_L} across reels"
best_reel = t[MAIN].max()

# ---------------- hero ----------------
avatar = (f'<img class="avatar" src="{esc(pic)}" alt="">' if pic
          else f'<div class="avatar">{esc((name or handle)[:1].upper())}</div>')
contact = (f'<a class="contact" href="mailto:{esc(email)}?subject=Partnership%20with%20%40{esc(handle)}">'
           f'Contact for partnerships</a>' if email else "")
st.markdown(f"""
<div class="hero">
  <div class="count glass">
    <span class="px"></span>
    <div class="n">{fmt_num(followers)}</div>
    <div class="l">followers on Instagram</div>
    <div class="stripes short" style="margin-top:22px"></div>
  </div>
  <div class="id glass">
    <h1>{esc(name or handle)}</h1>
    <div class="stripes" style="margin-top:14px"></div>
    <div class="row"><span class="handle">@{esc(handle)}</span>{avatar}</div>
    {f'<div class="bio">{esc(bio)}</div>' if bio else ''}
    {contact}
  </div>
</div>
<div class="board glass">
  <div><div class="v">{fmt_num(avg_views)}</div><div class="k">Average {MAIN_L} per reel</div></div>
  {f'<div><div class="v">{eng:.1%}</div><div class="k">Engagement rate</div></div>' if eng is not None and eng == eng
     else f'<div><div class="v">{len(t)}</div><div class="k">Reels published</div></div>'}
  <div><div class="v">{fmt_num(views_30)}</div><div class="k">{v30_label}</div></div>
  {f'<div><div class="v">+{fmt_num(gained)}</div><div class="k">New followers in 30 days</div><div class="d">{growth_pct:+.1%} growth</div></div>'
     if len(acct) > 1 else f'<div><div class="v">{fmt_num(best_reel)}</div><div class="k">{MAIN_L.capitalize()} on top reel</div></div>'}
</div>
""", unsafe_allow_html=True)

# ---------------- audience ----------------
def bars(df: pd.DataFrame, label_map=None, top=6, by_value=True) -> str:
    if by_value:
        df = df.sort_values("value", ascending=False).head(top)
    total = demo_totals[df["breakdown"].iloc[0]]
    peak = df["value"].max()
    rows = []
    for _, r in df.iterrows():
        lbl = label_map.get(r["label"], r["label"]) if label_map else r["label"]
        lbl = str(lbl).split(",")[0]
        p, w = r["value"] / total, r["value"] / peak
        rows.append(f'<div class="row"><span class="lbl">{esc(str(lbl))}</span>'
                    f'<span class="track"><span class="fill" style="width:{w*100:.1f}%;display:block"></span></span>'
                    f'<span class="pct">{"<1%" if p < .005 else f"{p:.0%}"}</span></div>')
    return '<div class="bars">' + "".join(rows) + "</div>"


if not demo.empty:
    demo_totals = demo.groupby("breakdown")["value"].sum()
    st.markdown("## Who's watching")
    st.markdown('<p class="lede">Follower breakdown reported by Instagram.</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        if "age" in demo_totals:
            age = demo[demo["breakdown"] == "age"].copy()
            age = age.sort_values("label")
            st.markdown("### Age")
            st.markdown('<div class="glass panel">' + bars(age, by_value=False) + "</div>", unsafe_allow_html=True)
        if "gender" in demo_totals:
            g = demo[demo["breakdown"] == "gender"].set_index("label")["value"]
            tot = g.sum()
            m, f = g.get("M", 0) / tot, g.get("F", 0) / tot
            st.markdown("### Gender")
            st.markdown(f"""<div class="glass panel"><div class="split"><span style="width:{m*100:.1f}%;background:{MOSS}"></span>
              <span style="width:{f*100:.1f}%;background:{LANE}"></span><span style="flex:1;background:{RULE}"></span></div>
              <div class="legend"><i style="background:{MOSS}"></i>Men {m:.0%} &nbsp;&nbsp;
              <i style="background:{LANE}"></i>Women {f:.0%}</div></div>""", unsafe_allow_html=True)
    with c2:
        if "city" in demo_totals:
            st.markdown("### Top cities")
            st.markdown('<div class="glass panel">' + bars(demo[demo["breakdown"] == "city"]) + "</div>", unsafe_allow_html=True)
        if "country" in demo_totals:
            names = {"US": "United States", "CA": "Canada", "GB": "United Kingdom", "AU": "Australia",
                     "MX": "Mexico", "KE": "Kenya", "DE": "Germany", "FR": "France", "BR": "Brazil",
                     "IN": "India", "JP": "Japan", "ES": "Spain", "IT": "Italy", "NZ": "New Zealand",
                     "NG": "Nigeria", "BE": "Belgium", "NL": "Netherlands", "IE": "Ireland", "PH": "Philippines",
                     "ZA": "South Africa", "NO": "Norway", "SE": "Sweden", "TT": "Trinidad and Tobago", "JM": "Jamaica"}
            st.markdown("### Top countries")
            st.markdown('<div class="glass panel">' + bars(demo[demo["breakdown"] == "country"], names, top=5) + "</div>", unsafe_allow_html=True)

# ---------------- top reels ----------------
st.markdown("## Top reels")
st.markdown(f'<p class="lede">Most-{"viewed" if HAS_VIEWS else "liked"} reels.</p>', unsafe_allow_html=True)
top = t[t["age_days"] <= 90].sort_values(MAIN, ascending=False).head(6)
if len(top) < 6:
    top = t.sort_values(MAIN, ascending=False).head(6)
cards = []
blooms = ["30% 25%", "70% 30%", "25% 70%", "65% 65%", "45% 20%", "20% 45%"]
for i, (_, r) in enumerate(top.iterrows()):
    has_img = isinstance(r["thumbnail_url"], str) and bool(r["thumbnail_url"])
    thumb = (f'<img src="{esc(r["thumbnail_url"])}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">' if has_img else
             f'<div class="ph">{esc(r["title"])}</div>')
    style = "" if has_img else (f'style="background: radial-gradient(55% 45% at {blooms[i % 6]}, #CDB592, transparent 70%),'
                                f' radial-gradient(70% 60% at {blooms[(i + 3) % 6]}, #7F9470, transparent 72%), #C9D2B8"')
    caption = f"{esc(r['title'])}, {r['posted_at']:%b %-d}" if has_img else f"Posted {r['posted_at']:%b %-d}"
    badge = '<span class="best">Top reel</span>' if i == 0 else ""
    cards.append(f"""
<a class="reel" href="{esc(r['permalink'] or '#')}" target="_blank" rel="noopener">
  <div class="thumb" {style}>{thumb}{badge}</div>
  <div class="card glass"><div class="meta"><div><b>{fmt_num(r[MAIN])}</b><span>{MAIN_L}</span></div>
       <div style="text-align:right"><b>{f"{r['engagement_rate']:.1%}" if HAS_VIEWS else fmt_num(r['comments'])}</b><span>{"engagement" if HAS_VIEWS else "comments"}</span></div></div>
  <div class="t">{caption}</div></div>
</a>""")
st.markdown('<div class="reels">' + "".join(cards) + "</div>", unsafe_allow_html=True)

# ---------------- growth ----------------
st.markdown("## Growth")
st.markdown('<p class="lede">Follower count and weekly views over time.</p>', unsafe_allow_html=True)
g1, g2 = st.columns(2, gap="large")
with g1:
    st.markdown("### Followers")
    f = acct[["captured_date", "followers"]]
    lo = f["followers"].min() * 0.97
    chart = alt.Chart(f).mark_area(
        line={"color": MOSS, "strokeWidth": 2.5},
        color=alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                           stops=[alt.GradientStop(color="rgba(143,175,120,0)", offset=0),
                                  alt.GradientStop(color="rgba(143,175,120,.22)", offset=1)]),
    ).encode(
        x=alt.X("captured_date:T", title=None, axis=alt.Axis(format="%b %-d", tickCount=5)),
        y=alt.Y("followers:Q", title=None, scale=alt.Scale(domain=[lo, f["followers"].max()]),
                axis=alt.Axis(format="~s", tickCount=4)),
        tooltip=[alt.Tooltip("captured_date:T", title="Date"), alt.Tooltip("followers:Q", format=",")],
    ).properties(height=240)
    st.altair_chart(chart, width="stretch")
with g2:
    st.markdown("### Weekly views")
    if daily["views"].notna().any():
        w = daily.set_index("captured_date")["views"].resample("W-SUN").sum().reset_index()
        w = w[(w["views"] > 0) & (w["captured_date"] <= daily["captured_date"].max())].tail(10)
        chart = alt.Chart(w).mark_bar(color=SAGE, size=26).encode(
            x=alt.X("captured_date:T", title=None, axis=alt.Axis(format="%b %-d", tickCount=5),
                    scale=alt.Scale(padding=20)),
            y=alt.Y("views:Q", title=None, axis=alt.Axis(format="~s", tickCount=4)),
            tooltip=[alt.Tooltip("captured_date:T", title="Week ending"), alt.Tooltip("views:Q", format=",")],
        ).properties(height=240)
        st.altair_chart(chart, width="stretch")
    else:
        st.caption("Weekly views appear after a few daily syncs.")

updated = snaps["captured_date"].max()
st.markdown(f'<div class="foot">Numbers come directly from the Instagram API and update daily. '
            f'Last updated {updated:%B %-d, %Y}.</div>', unsafe_allow_html=True)
