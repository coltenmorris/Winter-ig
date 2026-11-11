"""Partner-facing media kit."""
import html
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

import db
import flags as flags_mod

from shared import LANE, MOSS, SAGE, NAVY, SAND, SPLIT, RULE, cfg, fmt_num, load, video_table

media, snaps, acct, daily, demo, profile = load()
t_all = flags_mod.ensure_tags(video_table(media, snaps, window_days=30))
ads = t_all[t_all["is_ad"] == 1] if not t_all.empty else t_all          # brand partnerships portfolio
t = t_all[(t_all["kind"] == "reel") & (t_all["is_ad"] == 0)] if not t_all.empty else t_all  # organic reels only

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

# The same figures as they stood a month ago: reels posted up to 30 days ago, same window rules.
then = t[t["age_days"] >= 30].assign(age_days=lambda d: d["age_days"] - 30)
prev_recent = then[(then["age_days"] <= 90) & (then["age_days"] >= 3)]
if len(prev_recent) < 3:
    prev_recent = then
prev_avg = prev_recent[MAIN].mean() if len(prev_recent) else None
prev_eng = prev_recent["engagement_rate"].mean() if HAS_VIEWS and len(prev_recent) else None


def last_month(cur, prev, show):
    """'Last month X' line, with a green arrow only when the figure went up."""
    if prev is None or prev != prev or cur is None or cur != cur:
        return ""
    arrow = '<span class="up" aria-label="up from last month">&#9650;</span>' if cur > prev else ""
    return f'<div class="lm">{arrow}Last month {show(prev)}</div>'

d30 = daily[daily["captured_date"] > now - pd.Timedelta(days=30)]
views_30 = d30["views"].sum() if d30["views"].notna().any() else t[MAIN].sum()
v30_label = "Views in the last 30 days" if d30["views"].notna().any() else f"Total {MAIN_L} across reels"
best_reel = t[MAIN].max()

# ---------------- hero ----------------
avatar = (f'<img class="avatar" src="{esc(pic)}" alt="" referrerpolicy="no-referrer">' if pic
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
  <div><div class="v">{fmt_num(avg_views)}</div><div class="k">Average {MAIN_L} per reel</div>{last_month(avg_views, prev_avg, fmt_num)}</div>
  {f'<div><div class="v">{eng:.1%}</div><div class="k">Engagement rate</div>{last_month(eng, prev_eng, lambda x: f"{x:.1%}")}</div>' if eng is not None and eng == eng
     else f'<div><div class="v">{len(t)}</div><div class="k">Reels published</div></div>'}
  <div><div class="v">{fmt_num(views_30)}</div><div class="k">{v30_label}</div></div>
  {f'<div><div class="v">+{fmt_num(gained)}</div><div class="k">New followers in 30 days</div><div class="d">{growth_pct:+.1%} growth</div></div>'
     if len(acct) > 1 else f'<div><div class="v">{fmt_num(best_reel)}</div><div class="k">{MAIN_L.capitalize()} on top reel</div></div>'}
</div>
""", unsafe_allow_html=True)

# ---------------- audience ----------------
def change(p, prev_share):
    """Month-over-month change in percentage points; green arrow only when it went up."""
    if prev_share is None:
        return ""
    d = round((p - prev_share) * 100)
    if d > 0:
        return f'<span class="chg"><span class="up">&#9650;</span> +{d} pts</span>'
    return f'<span class="chg">{"no change" if d == 0 else f"{d} pts"}</span>'


def bars(df: pd.DataFrame, label_map=None, top=6, by_value=True) -> str:
    if by_value:
        df = df.sort_values("value", ascending=False).head(top)
    b = df["breakdown"].iloc[0]
    total = demo_totals[b]
    pshare = prev_share.get(b)
    peak = df["value"].max()
    rows = []
    for _, r in df.iterrows():
        lbl = label_map.get(r["label"], r["label"]) if label_map else r["label"]
        lbl = str(lbl).split(",")[0]
        p, w = r["value"] / total, r["value"] / peak
        rows.append(f'<div class="row"><span class="lbl">{esc(str(lbl))}</span>'
                    f'<span class="track"><span class="fill" style="width:{w*100:.1f}%;display:block"></span></span>'
                    f'<span class="pct">{"<1%" if p < .005 else f"{p:.0%}"}</span>'
                    + (change(p, pshare.get(r["label"], 0.0)) if pshare is not None else "") + "</div>")
    return f'<div class="bars{" mom" if pshare is not None else ""}">' + "".join(rows) + "</div>"


# Audience breakdowns: viewers this month (accounts reached) or followers, picked with a switch.
_all_demo = demo
_has_viewers = not demo.empty and demo["breakdown"].str.startswith("viewers:").any()
_has_followers = not demo.empty and (~demo["breakdown"].str.contains(":")).any()


def whole_percents(shares):
    """Round shares to whole percents that add up to exactly 100 (largest remainder)."""
    raw = [s * 100 for s in shares]
    out = [int(r) for r in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)[:100 - sum(out)]:
        out[i] += 1
    return out


class CountryNames(dict):
    """Two-letter country code -> full name (falls back to the code)."""
    def __bool__(self):  # an empty dict is falsy, which would skip the lookup
        return True

    def get(self, code, default=None):
        try:
            import pycountry
            c = pycountry.countries.get(alpha_2=code)
            if not c:
                return default or code
            return getattr(c, "common_name", None) or c.name
        except Exception:
            return default or code


def full_totals(d: pd.DataFrame) -> dict:
    """Instagram only lists the top 45 cities/countries, so shares use the whole audience
    (the gender or age breakdown covers everyone) rather than the sum of the listed rows."""
    sums = d.groupby("breakdown")["value"].sum().to_dict()
    whole = sums.get("gender") or sums.get("age")
    return {b: (whole if whole and b in ("city", "country") else s) for b, s in sums.items()}


prev_month = (pd.Timestamp.today().to_period("M") - 1).strftime("%Y-%m")
# Viewers "all time": Instagram only gives this week or this month, so add up every month the sync has saved.
_conn = db.connect()
_monthly = pd.read_sql("SELECT month, audience, breakdown, label, value FROM demographics_monthly", _conn)
_conn.close()
_vm = _monthly[_monthly["audience"] == "viewers"]
viewers_all = _vm.groupby(["breakdown", "label"], as_index=False)["value"].sum()
viewers_since = pd.Period(_vm["month"].min()).strftime("%B %Y") if not _vm.empty else None
_has_viewers = not viewers_all.empty
if _has_viewers or _has_followers:
    st.markdown("## Who's watching")
    options = (["Followers"] if _has_followers else []) + (["Viewers, all time"] if _has_viewers else [])
    pick = st.segmented_control("Audience", options, default=options[0], key="aud",
                                label_visibility="collapsed") or options[0]
    audience = "followers" if pick == "Followers" else "viewers"
    if audience == "viewers":
        demo = viewers_all
        demo_lede = (f"Everyone who viewed your posts and reels since {viewers_since}, added up month by month "
                     "(Instagram only reports viewers one month at a time).")
        prev_share = {}
    else:
        demo = _all_demo[~_all_demo["breakdown"].str.contains(":")]
        demo_lede = "Your followers, as reported by Instagram."
        _prev = _monthly[(_monthly["month"] == prev_month) & (_monthly["audience"] == "followers")]
        _ptot = full_totals(_prev) if not _prev.empty else {}
        prev_share = {b: (g.set_index("label")["value"] / _ptot[b]).to_dict() for b, g in _prev.groupby("breakdown")}
    demo_lede += " City and country shares are out of the whole audience; Instagram lists the top 45 of each."
    if audience == "followers":
        demo_lede += (f" Changes compare with {pd.Period(prev_month).strftime('%B')}." if prev_share else
                      " Month-over-month changes appear once last month's numbers are saved.")
else:
    demo = demo.iloc[0:0]
    prev_share = {}
if not demo.empty:
    demo_totals = full_totals(demo)
    st.markdown(f'<p class="lede">{demo_lede}</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        if "age" in demo_totals:
            age = demo[demo["breakdown"] == "age"].copy()
            age = age.sort_values("label")
            st.markdown("### Age")
            st.markdown('<div class="glass panel">' + bars(age, by_value=False) + "</div>", unsafe_allow_html=True)
        if "gender" in demo_totals:
            g = demo[demo["breakdown"] == "gender"].set_index("label")["value"]
            parts = [("Women", "F", LANE), ("Men", "M", MOSS), ("Not specified", "U", RULE)]
            shares = [g.get(code, 0) / g.sum() for _, code, _ in parts]
            pcts = whole_percents(shares)
            pg = prev_share.get("gender")
            st.markdown("### Gender")
            bar = "".join(f'<span style="width:{s*100:.2f}%;background:{col}"></span>' for (_, _, col), s in zip(parts, shares))
            legend = " &nbsp;&nbsp; ".join(
                f'<span style="white-space:nowrap"><i style="background:{col}"></i>{name} {p}%'
                f'{change(s, pg.get(code, 0.0)) if pg else ""}</span>'
                for (name, code, col), s, p in zip(parts, shares, pcts))
            st.markdown(f'<div class="glass panel"><div class="split">{bar}</div><div class="legend">{legend}</div>'
                        f'<p class="note" style="margin-top:10px">"Not specified" is people who haven\'t shared a gender with Instagram.</p></div>',
                        unsafe_allow_html=True)
    with c2:
        if "city" in demo_totals:
            st.markdown("### Top cities")
            st.markdown('<div class="glass panel">' + bars(demo[demo["breakdown"] == "city"]) + "</div>", unsafe_allow_html=True)
        if "country" in demo_totals:
            names = CountryNames()
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

# ---------------- brand partnerships ----------------
if not ads.empty:
    st.markdown("## Brand partnerships")
    ad_main = "views" if ads["views"].notna().any() else "likes"
    a_avg, o_avg = ads[ad_main].mean(), t[ad_main].mean() if not t.empty else None
    a_eng = ads["engagement_rate"].mean()
    vs = (f"{(a_avg / o_avg - 1):+.0%} vs. a typical reel" if o_avg and a_avg == a_avg else "")
    brands = sorted({b for b in ads["brand"] if b})
    st.markdown(f'<p class="lede">Sponsored posts and reels{" for " + ", ".join(esc(b) for b in brands) if brands else ""}, '
                f'and how they typically perform.</p>', unsafe_allow_html=True)
    st.markdown(f"""<div class="board glass" style="margin-top:8px">
      <div><div class="v">{len(ads)}</div><div class="k">Sponsored {"post" if len(ads) == 1 else "posts"}</div></div>
      <div><div class="v">{fmt_num(a_avg)}</div><div class="k">Average {ad_main} per ad</div><div class="d">{vs}</div></div>
      <div><div class="v">{f"{a_eng:.1%}" if a_eng == a_eng else "n/a"}</div><div class="k">Average engagement on ads</div></div>
      <div><div class="v">{fmt_num(ads[ad_main].sum())}</div><div class="k">Total {ad_main} delivered</div></div>
    </div>""", unsafe_allow_html=True)
    acards = []
    for _, r in ads.sort_values("posted_at", ascending=False).iterrows():
        has_img = isinstance(r["thumbnail_url"], str) and bool(r["thumbnail_url"])
        thumb = (f'<img src="{esc(r["thumbnail_url"])}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
                 if has_img else f'<div class="ph">{esc(r["title"])}</div>')
        badge = f'<span class="best">{esc(r["brand"])}</span>' if r["brand"] else ""
        eng = f"{r['engagement_rate']:.1%}" if pd.notna(r["engagement_rate"]) else "n/a"
        acards.append(f"""
<a class="reel" href="{esc(r['permalink'] or '#')}" target="_blank" rel="noopener">
  <div class="thumb">{thumb}{badge}</div>
  <div class="card glass"><div class="meta"><div><b>{fmt_num(r[ad_main])}</b><span>{ad_main}</span></div>
       <div style="text-align:right"><b>{eng}</b><span>engagement</span></div></div>
  <div class="t">{esc(r['title'])}, {r['posted_at']:%b %-d, %Y}</div></div>
</a>""")
    st.markdown('<div class="reels" style="margin-top:22px">' + "".join(acards) + "</div>", unsafe_allow_html=True)

# ---------------- growth (hidden until there's a trend to show) ----------------
fol_pts = acct[["captured_date", "followers"]].dropna()
show_fol = fol_pts["captured_date"].nunique() >= 2
wk = pd.DataFrame()
if daily["views"].notna().any():
    wk = daily.set_index("captured_date")["views"].resample("W-SUN").sum().reset_index()
    wk = wk[(wk["views"] > 0) & (wk["captured_date"] <= daily["captured_date"].max())].tail(10)
show_wk = len(wk) >= 2
if show_fol or show_wk:
    st.markdown("## Growth")
    st.markdown('<p class="lede">' + " and ".join(x for x, ok in (("Follower count", show_fol), ("weekly views", show_wk)) if ok)
                + ' over time.</p>', unsafe_allow_html=True)
    cols = st.columns(2, gap="large") if (show_fol and show_wk) else [st.container()]
    ci = 0
    if show_fol:
        with cols[ci]:
            st.markdown("### Followers")
            lo = fol_pts["followers"].min() * 0.97
            chart = alt.Chart(fol_pts).mark_area(
                line={"color": MOSS, "strokeWidth": 2.5},
                color=alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                                   stops=[alt.GradientStop(color="rgba(143,175,120,0)", offset=0),
                                          alt.GradientStop(color="rgba(143,175,120,.22)", offset=1)]),
            ).encode(
                x=alt.X("captured_date:T", title=None, axis=alt.Axis(format="%b %-d", tickCount=5)),
                y=alt.Y("followers:Q", title=None, scale=alt.Scale(domain=[lo, fol_pts["followers"].max()]),
                        axis=alt.Axis(format="~s", tickCount=4)),
                tooltip=[alt.Tooltip("captured_date:T", title="Date"), alt.Tooltip("followers:Q", format=",")],
            ).properties(height=240)
            st.altair_chart(chart, width="stretch")
        ci = min(ci + 1, len(cols) - 1)
    if show_wk:
        with cols[ci]:
            st.markdown("### Weekly views")
            chart = alt.Chart(wk).mark_bar(color=SAGE, size=26).encode(
                x=alt.X("captured_date:T", title=None, axis=alt.Axis(format="%b %-d", tickCount=5),
                        scale=alt.Scale(padding=20)),
                y=alt.Y("views:Q", title=None, axis=alt.Axis(format="~s", tickCount=4)),
                tooltip=[alt.Tooltip("captured_date:T", title="Week ending"), alt.Tooltip("views:Q", format=",")],
            ).properties(height=240)
            st.altair_chart(chart, width="stretch")

updated = snaps["captured_date"].max()
st.markdown(f'<div class="foot">Numbers come directly from the Instagram API and update daily. '
            f'Last updated {updated:%B %-d, %Y}.</div>', unsafe_allow_html=True)
