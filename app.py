"""Instagram video analytics dashboard.  Run with:  streamlit run app.py"""
import pandas as pd
import streamlit as st

import db
from ig_client import InstagramError
from sync import run_sync

st.set_page_config(page_title="IG Video Analytics", page_icon="📈", layout="wide")


@st.cache_data(ttl=60)
def load():
    conn = db.connect()
    media = pd.read_sql("SELECT * FROM media", conn)
    snaps = pd.read_sql("SELECT * FROM media_snapshots", conn)
    acct = pd.read_sql("SELECT * FROM account_snapshots ORDER BY captured_date", conn)
    conn.close()
    for df, col in ((snaps, "captured_date"), (acct, "captured_date")):
        df[col] = pd.to_datetime(df[col])
    media["posted_at"] = pd.to_datetime(media["posted_at"], utc=True).dt.tz_localize(None)
    return media, snaps, acct


# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Data")
    if st.button("Sync now", type="primary", width="stretch"):
        box = st.empty()
        lines = []
        try:
            run_sync(log=lambda m: (lines.append(m), box.code("\n".join(lines))))
            st.success("Synced.")
            st.cache_data.clear()
        except InstagramError as e:
            st.error(f"Instagram error: {e}")
    window = st.selectbox("Trend window", [7, 14, 30, 90], index=0, format_func=lambda d: f"Last {d} days")
    st.caption("Stats can lag up to 48 hours on Instagram's side.")

media, snaps, acct = load()
st.title("📈 Instagram Video Analytics")

if snaps.empty:
    st.info("No data yet. Tap **Sync now** in the sidebar, or run `python sync.py --demo` to preview with fake data.")
    st.stop()

# ---------------- derived tables ----------------
snaps = snaps.sort_values(["media_id", "captured_date"])
latest_date = snaps["captured_date"].max()
cutoff = latest_date - pd.Timedelta(days=window)

latest = snaps.groupby("media_id").tail(1).set_index("media_id")
# Each video's stats as of the start of the window (0 if posted after it).
before = (snaps[snaps["captured_date"] <= cutoff].groupby("media_id").tail(1)
          .set_index("media_id").reindex(latest.index).fillna(0))

table = media.set_index("id").join(latest, how="inner")
table["views_gained"] = latest["views"] - before["views"]
table["engagement_rate"] = (table["total_interactions"] / table["views"].replace(0, pd.NA)).astype(float)
table["avg_watch_s"] = table["avg_watch_ms"] / 1000
table["title"] = table["caption"].fillna("(no caption)").str.split("\n").str[0].str.slice(0, 60)
table["type"] = table["is_trial"].map({1: "Trial reel", 0: "Reel"})

# Daily views gained across all videos (difference between consecutive snapshots).
snaps["views_delta"] = snaps.groupby("media_id")["views"].diff().fillna(snaps["views"])
daily = snaps[snaps["captured_date"] > cutoff].groupby("captured_date")["views_delta"].sum()

# ---------------- KPIs ----------------
c1, c2, c3, c4 = st.columns(4)
followers_now = acct["followers"].iloc[-1] if not acct.empty else None
acct_before = acct[acct["captured_date"] <= cutoff]
followers_then = acct_before["followers"].iloc[-1] if not acct_before.empty else (acct["followers"].iloc[0] if not acct.empty else None)
c1.metric("Followers", f"{followers_now:,}" if followers_now is not None else "n/a",
          f"{followers_now - followers_then:+,}" if followers_now is not None else None)
c2.metric(f"Views gained ({window}d)", f"{int(table['views_gained'].sum()):,}")
c3.metric("Avg engagement rate", f"{table['engagement_rate'].mean():.1%}")
c4.metric("Videos tracked", len(table))

# ---------------- charts ----------------
left, right = st.columns(2)
with left:
    st.subheader("Views gained per day")
    st.bar_chart(daily, height=260)
with right:
    st.subheader("Followers")
    if not acct.empty:
        st.line_chart(acct.set_index("captured_date")["followers"], height=260)

st.subheader(f"Top videos by views gained (last {window} days)")
top = table.sort_values("views_gained", ascending=False)
st.bar_chart(top.head(10).set_index("title")["views_gained"], horizontal=True, height=320)

# ---------------- table with trial flag ----------------
st.subheader("All videos")
st.caption("Tick **Trial** for reels you posted as trial reels so you can compare them below.")
show = top.reset_index()[["id", "is_trial", "title", "posted_at", "views", "views_gained", "likes",
                          "comments", "shares", "saved", "engagement_rate", "avg_watch_s",
                          "skip_rate", "permalink"]]
show["is_trial"] = show["is_trial"].astype(bool)
edited = st.data_editor(
    show, hide_index=True, width="stretch", disabled=[c for c in show.columns if c != "is_trial"],
    column_config={
        "id": None,
        "is_trial": st.column_config.CheckboxColumn("Trial"),
        "title": "Video",
        "posted_at": st.column_config.DateColumn("Posted"),
        "views_gained": st.column_config.NumberColumn(f"+Views ({window}d)"),
        "engagement_rate": st.column_config.NumberColumn("Engagement", format="percent"),
        "avg_watch_s": st.column_config.NumberColumn("Avg watch (s)", format="%.1f"),
        "skip_rate": st.column_config.NumberColumn("Skip rate", format="percent"),
        "permalink": st.column_config.LinkColumn("Link", display_text="Open"),
    },
)
changed = edited[edited["is_trial"] != show["is_trial"]]
if not changed.empty:
    conn = db.connect()
    for _, r in changed.iterrows():
        db.set_trial(conn, r["id"], bool(r["is_trial"]))
    conn.close()
    st.cache_data.clear()
    st.rerun()

# ---------------- per-video trend ----------------
st.subheader("Single video trend")
pick = st.selectbox("Video", top.index, format_func=lambda i: f"{top.loc[i, 'title']} ({top.loc[i, 'posted_at']:%b %d})")
one = snaps[snaps["media_id"] == pick].set_index("captured_date")
st.line_chart(one[["views", "reach"]], height=260)

# ---------------- trial vs regular ----------------
if table["is_trial"].sum() > 0:
    st.subheader("Trial reels vs regular reels")
    comp = table.groupby("type").agg(
        videos=("views", "size"), avg_views=("views", "mean"),
        avg_engagement=("engagement_rate", "mean"), avg_watch_s=("avg_watch_s", "mean"),
        avg_skip_rate=("skip_rate", "mean"),
    )
    st.dataframe(comp.style.format({"avg_views": "{:,.0f}", "avg_engagement": "{:.1%}",
                                    "avg_watch_s": "{:.1f}", "avg_skip_rate": "{:.1%}"}),
                 width="stretch")
