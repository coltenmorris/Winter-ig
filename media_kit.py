"""Partner-facing media kit."""
import html

import pandas as pd
import streamlit as st

import db
import flags as flags_mod

import editorial as ed
from shared import cfg, fmt_num, load, video_table

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

recent = t[(t["age_days"] <= 90) & (t["age_days"] >= 3)]
recent_label = "last 90 days"
if len(recent) < 3:
    recent, recent_label = t, "all time"
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
    arrow = '<i class="ed-up" title="up from last month">&#9650;</i> ' if cur > prev else ""
    return f'<div class="lm">{arrow}Last month {show(prev)}</div>'

d30 = daily[daily["captured_date"] > now - pd.Timedelta(days=30)]
# Prefer Instagram's own 30-day total; otherwise only sum daily numbers once they cover the full 30 days.
_c = db.connect()
_v30 = _c.execute("SELECT value FROM settings WHERE key='views_30d'").fetchone()
_c.close()
if _v30 and _v30[0] not in (None, "", "None"):
    views_30, v30_label = float(_v30[0]), "Views in the last 30 days"
elif d30["views"].notna().sum() >= 28:
    views_30, v30_label = d30["views"].sum(), "Views in the last 30 days"
else:
    views_30, v30_label = t[MAIN].sum(), f"Total {MAIN_L} across reels"
best_reel = t[MAIN].max()

# ---------------- hero ----------------
created = cfg("ACCOUNT_CREATED", "June 15th, 2026")
avatar = (f'<img class="avatar" src="{esc(pic)}" alt="" referrerpolicy="no-referrer">' if pic
          else f'<div class="avatar">{esc((name or handle)[:1].upper())}</div>')
contact = (f'<a class="contact" href="mailto:{esc(email)}?subject=Partnership%20with%20%40{esc(handle)}">'
           f'Contact for partnerships</a>' if email else "")
id_html = f"""  <div class="id glass">
    <h1>{esc(name or handle)}</h1>
    <div class="stripes" style="margin-top:14px"></div>
    <div class="row"><span class="handle">@{esc(handle)}</span>{avatar}</div>
    {f'<div class="bio">{esc(bio)}</div>' if bio else ''}
    {f'<div class="created">Account created {esc(created)}</div>' if created else ''}
    {contact}
  </div>
"""
# ---------------- editorial cover (laid out after the PDF media kit) ----------------
ed.inject()
KIT = ed.content()
SEC = ed.Sections(name or handle)
_c = db.connect()
_v90 = _c.execute("SELECT value FROM settings WHERE key='views_90d'").fetchone()
_c.close()
views_90 = float(_v90[0]) if _v90 and _v90[0] not in (None, "", "None") else None
cover_img = ed.asset("kit/cover.jpg") or pic
_name_lines = "<br>".join(esc(w) for w in (name or handle).split())
cover_html = f"""<div class="ed-cover">
  <div class="ed-panel">
    <div class="ed-k">Creator / Media kit</div><hr>
    <div class="ed-name">{_name_lines}</div>
    <div class="ed-cats">{"".join(f"<div>{esc(c)}</div>" for c in KIT.get("categories", []))}</div><hr>
    <div class="ed-stat"><b>{fmt_num(followers)}</b><span>Instagram followers</span></div>
    {f'<div class="ed-stat"><b>{fmt_num(views_90)}</b><span>90 day views</span></div>' if views_90 else ""}
    <div class="ed-panel-foot"><div class="h">@{esc(handle)}</div><div class="d">{now:%B %Y}</div>{contact}</div>
  </div>
  <div class="ed-photo">{f'<img src="{esc(cover_img)}" alt="{esc(name or handle)}" referrerpolicy="no-referrer">' if cover_img else ""}</div>
</div>"""
_about = KIT.get("about") or ([bio] if bio else [])
_pillars = KIT.get("pillars", [])
_pimg = ed.asset("kit/profile.jpg")
profile_html = SEC.head("Profile", "The creator") + f"""<div class="ed-profile">
  {f'<div class="ed-pimg"><img src="{esc(_pimg)}" alt="{esc(name or handle)}"></div>' if _pimg else ""}
  <div>
    <div class="ed-about"><h4>{esc(KIT.get("about_title") or "About")}</h4>{"".join(f"<p>{esc(x)}</p>" for x in _about)}
      {f'<div class="created">Account created {esc(created)}</div>' if created else ""}</div>
    {('<div class="ed-label">Content pillars</div><ol class="ed-pillars">'
      + "".join(f"<li><span>{i}</span>{esc(x)}</li>" for i, x in enumerate(_pillars, 1)) + "</ol>") if _pillars else ""}
  </div>
</div>"""

# Time-range switch for the first three numbers (90 days by default). The switch is drawn just above
# the numbers, but its current value is read here so the numbers match it.
WINDOWS = ["Last 30 days", "Last 90 days", "All time"]
win = st.session_state.get("win") or "Last 90 days"
_c = db.connect()
_setting = lambda k: (lambda r: float(r[0]) if r and r[0] not in (None, "", "None") else None)(
    _c.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone())
_done = t[t["age_days"] >= 3]  # reels still collecting views are left out
if win == "Last 30 days":
    w_pool, w_label, w_views, w_vlabel = _done[_done["age_days"] <= 30], "last 30 days", views_30, v30_label
elif win == "All time":
    w_pool, w_label = (_done if len(_done) else t), "all time"
    w_views, w_vlabel = _setting("views_all"), "Views, all time"
else:
    w_pool, w_label, w_views, w_vlabel = recent, recent_label, _setting("views_90d"), "Views in the last 90 days"
_c.close()
w_avg = w_pool[MAIN].mean() if len(w_pool) else None
w_eng = w_pool["engagement_rate"].mean() if HAS_VIEWS and len(w_pool) else None
_show = lambda v, f: f(v) if v is not None and v == v else "n/a"


def _sum(col):
    return w_pool[col].sum(min_count=1) if col in w_pool and len(w_pool) else None


_win_title = {"Last 30 days": "last 30 days", "Last 90 days": "last 90 days", "All time": "all time"}[win]
_through = f"{now:%B %-d, %Y}"
signals = [(lbl, _sum(col)) for lbl, col in (("Likes", "likes"), ("Saves", "saved"), ("Shares", "shares"), ("Reposts", "reposts"))]
signals = [(lbl, v) for lbl, v in signals if v is not None and v == v]
board_html = f"""<div class="ed-tiles">
  <div class="ed-tile"><b>{_show(w_views, fmt_num)}</b><span>{"Total views" if w_views is not None else w_vlabel}</span></div>
  <div class="ed-tile"><b>{_show(w_avg, fmt_num)}</b><span>Average {MAIN_L} per reel</span>{last_month(w_avg, prev_avg, fmt_num) if win == "Last 90 days" else ""}</div>
  {f'<div class="ed-tile"><b>{_show(w_eng, lambda x: f"{x:.1%}")}</b><span>Engagement rate</span>{last_month(w_eng, prev_eng, lambda x: f"{x:.1%}") if win == "Last 90 days" else ""}</div>' if HAS_VIEWS
     else f'<div class="ed-tile"><b>{len(w_pool)}</b><span>Reels published</span></div>'}
  <div class="ed-tile"><b>{fmt_num(best_reel)}</b><span>{MAIN_L.capitalize()} on top reel (all time)</span></div>
</div>
<div class="ed-band" aria-hidden="true"></div>
<p class="ed-fine">{fmt_num(t[MAIN].sum())} total {MAIN_L} across all {len(t)} reels / reel averages use reels in the {esc(w_label)} that are at least 3 days old</p>
""" + (f"""<div class="ed-label">Engagement signals / reels, {esc(w_label)}</div>
<div class="ed-signals">{"".join(f'<div><b>{fmt_num(v)}</b><span>{lbl}</span></div>' for lbl, v in signals)}</div>""" if signals else "") + \
    '<p class="ed-fine" style="margin-top:34px">Metrics come straight from the Instagram API; figures are rounded.</p>'


def board_block():
    """Performance section, with the time-range switch sitting right above the numbers it controls."""
    st.markdown(SEC.head("Performance", f"Performance / {_win_title}",
                         f"Instagram performance / {_win_title}, through {_through}"), unsafe_allow_html=True)
    with st.container(key="winbox"):
        st.segmented_control("Time range", WINDOWS, default="Last 90 days", key="win", label_visibility="collapsed")
        st.markdown(board_html, unsafe_allow_html=True)


live_on = st.session_state.get("live_kit", False)
if live_on:
    # Live count takes the place of the big follower number (switch is at the bottom of the page)
    from live import live_followers
    left, right = st.columns([7, 5], vertical_alignment="bottom")
    with left:
        st.markdown(f'<div class="hero solo">{id_html}</div>', unsafe_allow_html=True)
    with right:
        live_followers(int(followers), hero=True)
else:
    st.markdown(cover_html, unsafe_allow_html=True)
st.markdown(profile_html, unsafe_allow_html=True)
board_block()

# ---------------- audience ----------------
def change(p, prev_share):
    """Month-over-month change in percentage points; green arrow only when it went up."""
    if prev_share is None:
        return ""
    d = round((p - prev_share) * 100)
    if d > 0:
        return f'<span class="chg"><span class="up">&#9650;</span> +{d} pts</span>'
    return f'<span class="chg">{"no change" if d == 0 else f"{d} pts"}</span>'


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


def age_buckets(age: pd.Series) -> list[tuple[str, float, list[str]]]:
    """Age groups as on the PDF: 13-17 ... 35-44, then everything 45 and over together."""
    young = [(k, float(v), [k]) for k, v in sorted(age.items()) if not str(k)[:2].isdigit() or int(str(k)[:2]) < 45]
    older = [k for k in age.index if str(k)[:2].isdigit() and int(str(k)[:2]) >= 45]
    return young + ([("45+", float(age[older].sum()), older)] if older else [])


pct1 = lambda x: f"{x:.1%}"
prev_month = (pd.Timestamp.today().to_period("M") - 1).strftime("%Y-%m")
_all_demo = demo
_has_followers = not demo.empty and (~demo["breakdown"].str.contains(":")).any()
# Viewers "all time": Instagram only gives this week or this month, so add up every month the sync has saved.
_conn = db.connect()
_monthly = pd.read_sql("SELECT month, audience, breakdown, label, value FROM demographics_monthly", _conn)
_conn.close()
_vm = _monthly[_monthly["audience"] == "viewers"]
viewers_all = _vm.groupby(["breakdown", "label"], as_index=False)["value"].sum()
viewers_since = pd.Period(_vm["month"].min()).strftime("%B %Y") if not _vm.empty else None
_has_viewers = not viewers_all.empty
if _has_viewers or _has_followers:
    options = (["Followers"] if _has_followers else []) + (["Viewers, all time"] if _has_viewers else [])
    _pick = st.session_state.get("aud") or options[0]
    audience = "viewers" if _pick == "Viewers, all time" and _has_viewers else ("followers" if _has_followers else "viewers")
    st.markdown(SEC.head("Audience", KIT.get("audience_title") or "Who's watching",
                         "Follower demographics / Instagram Insights" if audience == "followers"
                         else f"Viewer demographics / everyone who viewed since {viewers_since}"), unsafe_allow_html=True)
    st.segmented_control("Audience", options, default=options[0], key="aud", label_visibility="collapsed")
    if audience == "viewers":
        demo = viewers_all
        demo_lede = ("Viewers are added up month by month, because Instagram only reports them one month at a time.")
        prev_share = {}
    else:
        demo = _all_demo[~_all_demo["breakdown"].str.contains(":")]
        demo_lede = ""
        _prev = _monthly[(_monthly["month"] == prev_month) & (_monthly["audience"] == "followers")]
        _ptot = full_totals(_prev) if not _prev.empty else {}
        prev_share = {b: (g.set_index("label")["value"] / _ptot[b]).to_dict() for b, g in _prev.groupby("breakdown")}
        if prev_share:
            demo_lede = f"Changes compare with {pd.Period(prev_month).strftime('%B')}."
else:
    demo = demo.iloc[0:0]
    prev_share = {}
if not demo.empty:
    demo_totals = full_totals(demo)
    series = lambda b: demo[demo["breakdown"] == b].set_index("label")["value"]
    tiles = []
    if "gender" in demo_totals:
        g = series("gender")
        _fm = g.get("F", 0) + g.get("M", 0)  # like Instagram's own Insights: share of people who list a gender
        if _fm:
            tiles.append(f'<div class="ed-tile dark"><b>{pct1(g.get("F", 0) / _fm)}</b><span>Female</span></div>')
    if "age" in demo_totals:
        a = series("age")
        core = a[[k for k in a.index if k in ("18-24", "25-34")]].sum()
        tiles.append(f'<div class="ed-tile"><b>{pct1(core / a.sum())}</b><span>Ages 18-34</span></div>')
    h = f'<div class="ed-tiles big">{"".join(tiles)}</div>' if tiles else ""
    if "gender" in demo_totals:
        g = series("gender")
        _fm = g.get("F", 0) + g.get("M", 0)
        if _fm:
            h += (f'<p class="ed-fine">Female share is out of people who list a gender, as in Instagram Insights '
                  f'(men {pct1(g.get("M", 0) / _fm)}). {pct1(g.get("U", 0) / g.sum())} of the audience '
                  "hasn&#39;t shared a gender with Instagram.</p>")
    if "age" in demo_totals:
        a, pa = series("age"), prev_share.get("age")
        rows = age_buckets(a)
        peak = max(v for _, v, _ in rows) or 1
        tot = a.sum()
        h += '<div class="ed-label">Age distribution</div><div class="ed-bars">' + "".join(
            f'<div class="r"><span>{esc(str(k))}</span><span class="t"><span class="f" style="width:{v / peak * 100:.1f}%"></span></span>'
            f'<span class="p">{pct1(v / tot)}{change(v / tot, sum(pa.get(x, 0.0) for x in keys)) if pa else ""}</span></div>'
            for k, v, keys in rows) + "</div>"
    if "country" in demo_totals:
        c = series("country").sort_values(ascending=False).head(5)
        names = CountryNames()
        items = [f"{esc(names.get(k, k))} {pct1(v / demo_totals['country'])}" for k, v in c.items()]
        h += ('<div class="ed-label">Top countries</div><div class="ed-countries">' + " / ".join(items[:3])
              + ("<br>" + " / ".join(items[3:]) if len(items) > 3 else "") + "</div>")
    _c = db.connect()
    _ref = _c.execute("SELECT value FROM settings WHERE key=?", (f"demo_refreshed_{audience}",)).fetchone()
    _c.close()
    notes = [demo_lede, "Country shares are out of the whole audience."]
    if _ref and _ref[0]:
        notes.append(f"Instagram last updated these numbers on {pd.Timestamp(_ref[0]):%B %-d, %Y}.")
    h += f'<p class="ed-fine" style="margin-top:30px">{" ".join(n for n in notes if n)}</p>'
    st.markdown(h, unsafe_allow_html=True)

# ---------------- top reels ----------------
st.markdown(SEC.head("Content", "Top-performing reels",
                     f'Most-{"viewed" if HAS_VIEWS else "liked"} reels / tap one to open it on Instagram'),
            unsafe_allow_html=True)
top_range = st.segmented_control("Top reels range", ["All time", "Last 90 days"], default="All time",
                                 key="top_range", label_visibility="collapsed") or "All time"
pool_top = t if top_range == "All time" else t[t["age_days"] <= 90]
top = pool_top.sort_values(MAIN, ascending=False).head(6)
if top.empty:
    st.markdown('<p class="lede">No reels posted in the last 90 days.</p>', unsafe_allow_html=True)
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
deals = [d for d in KIT.get("partnerships", []) if d.get("brand")]
if deals or not ads.empty:
    h = SEC.head("Partnerships", KIT.get("partnerships_title") or "Brand partnerships",
                 KIT.get("partnerships_sub") or "Brand partnerships")
    if deals:
        vals = [float(d.get("value") or 0) for d in deals]
        money = lambda v: f"${v:,.0f}"
        h += (f'<div class="ed-deal"><b>{money(sum(vals))}</b><div><h4>Confirmed partnership value</h4>'
              f'<p>{len(deals)} brand {"partner" if len(deals) == 1 else "partners"}'
              + (f' / {money(float(KIT["top_rate"]))} top Reel rate' if KIT.get("top_rate") else "") + '</p></div></div>'
              '<div class="ed-brands">' + "".join(
                  f'<div class="ed-brand"><div><b>{esc(d["brand"])}</b><span>{esc(d.get("detail", ""))}</span></div>'
                  f'<em>{money(float(d.get("value") or 0)) if d.get("value") else ""}</em></div>' for d in deals) + "</div>")
        if KIT.get("partnerships_note"):
            h += f'<p class="ed-fine" style="margin-top:26px">{esc(KIT["partnerships_note"])}</p>'
    st.markdown(h, unsafe_allow_html=True)
if not ads.empty:
    ad_main = "views" if ads["views"].notna().any() else "likes"
    a_avg, o_avg = ads[ad_main].mean(), t[ad_main].mean() if not t.empty else None
    a_eng = ads["engagement_rate"].mean()
    vs = (f"{(a_avg / o_avg - 1):+.0%} vs. a typical reel" if o_avg and a_avg == a_avg else "")
    st.markdown(f"""<div class="ed-label">Sponsored posts / how they perform</div><div class="ed-tiles">
      <div class="ed-tile"><b>{len(ads)}</b><span>Sponsored {"post" if len(ads) == 1 else "posts"}</span></div>
      <div class="ed-tile"><b>{fmt_num(a_avg)}</b><span>Average {ad_main} per ad</span><div class="lm">{vs}</div></div>
      <div class="ed-tile"><b>{f"{a_eng:.1%}" if a_eng == a_eng else "n/a"}</b><span>Average engagement on ads</span></div>
      <div class="ed-tile"><b>{fmt_num(ads[ad_main].sum())}</b><span>Total {ad_main} delivered</span></div>
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

# ---------------- original Instagram Insights (screenshot gallery) ----------------
_gallery = ed.gallery_html()
if _gallery:
    st.markdown(SEC.head("Original insights", "Original Instagram Insights",
                         "Source screenshots from Instagram's professional dashboard / supplied by creator. "
                         "Tap one to see it full size.") + _gallery, unsafe_allow_html=True)

updated = snaps["captured_date"].max()
st.markdown(f'<div class="ed-foot"><span>@{esc(handle)} / Creator media kit</span>'
            f'<span>Numbers come directly from the Instagram API and update daily. Last updated {updated:%B %-d, %Y}.</span></div>',
            unsafe_allow_html=True)

# ---------------- live follower count (off by default, switch at the very bottom) ----------------
st.toggle("Show live follower count", value=False, key="live_kit",
          help="Replaces the follower number at the top with a live count that updates every 5 seconds.")
