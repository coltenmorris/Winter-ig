# Instagram Media Kit & Analytics

Two pages in one app:

- **Media kit** (the main link): a polished page for brands with your follower count,
  average views, engagement rate, audience demographics, top reels and growth.
- **Creator analytics** (add `/creator` to the link): private insights on when to post,
  which topics pull views, hook strength, early velocity and trial reels.
- **Posting calendar** (add `/calendar` to the link): a heatmap of how often you post, with
  views or engagement on each day. Tap a day to see its reels, then open any reel for its
  first 24 hours, first week and to-date stats.

If the daily sync fails with "Cannot parse access token", re-copy the token from the Meta
dashboard's **Generate access tokens** section and paste only the token (it starts with `IG`)
into the `IG_ACCESS_TOKEN` secret.

A local dashboard that pulls your Instagram video stats (views, reach, likes, comments,
shares, saves, watch time, skip rate) into a database every day and charts the trends.

## Run it in the cloud (no computer needed)

**Daily sync (GitHub Actions)**
1. Repo **Settings → Secrets and variables → Actions → New repository secret**:
   name `IG_ACCESS_TOKEN`, value = your token.
2. **Actions** tab → **Daily Instagram sync** → **Run workflow** to test it. After that it
   runs every morning and saves stats to `ig_analytics.db` in the repo.
3. Optional, for automatic token renewal: create a fine-grained GitHub token with
   **Secrets: read and write** on this repo and save it as a secret named `GH_PAT`.
   Without it, replace `IG_ACCESS_TOKEN` with a fresh token every ~60 days
   (GitHub emails you if the sync starts failing).

**Dashboard (Streamlit Community Cloud)**
1. Sign in at share.streamlit.io with GitHub → **Create app** → pick this repo,
   branch `main`, file `app.py` → **Deploy**.
2. In the app's **Settings → Secrets**, paste:
   ```
   CONTACT_EMAIL = "you@example.com"       # shows a "Contact for partnerships" button
   DASHBOARD_PASSWORD = "pick-a-password"  # protects the /creator page
   CREATOR_TAGLINE = "One line about your content"   # optional, overrides your IG bio
   CREATOR_NAME = "Your Name"                        # optional
   IG_ACCESS_TOKEN = "your token"          # optional, makes Sync now work on the site
   ```

Keep the repo **private**, since your stats are committed to it.

## Run it on your own computer

### 1. Install (one time)

You need Python 3.10 or newer. Get the code and open a terminal in the folder:

```
git clone https://github.com/<your-username>/winter-ig.git
cd winter-ig
python -m venv .venv
# Mac/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Add your token

1. Copy `.env.example` to a new file named `.env`
2. Paste your Instagram access token after `IG_ACCESS_TOKEN=`
3. Save. Never share or upload `.env`.

### 3. Run it

```
python sync.py          # pulls your stats (first run takes a minute)
streamlit run app.py    # opens the dashboard in your browser
```

You can also press **Sync now** inside the dashboard.

Want to see it before connecting? `python sync.py --demo` fills it with fake data.
Delete `ig_analytics.db` afterwards to start fresh with your real stats.

### 4. Sync automatically every day

Trends build from daily snapshots, so schedule `sync.py` once a day.

**Mac/Linux** (runs 9am daily): run `crontab -e` and add
```
0 9 * * * cd /full/path/to/ig-analytics && .venv/bin/python sync.py >> sync.log 2>&1
```

**Windows**: open Task Scheduler → Create Basic Task → Daily → Action "Start a program":
- Program: `C:\full\path\to\ig-analytics\.venv\Scripts\python.exe`
- Arguments: `sync.py`
- Start in: `C:\full\path\to\ig-analytics`

## Notes

- **Token refresh:** tokens last 60 days. `sync.py` refreshes it automatically every
  7 days, as long as it runs at least once in a while. If it ever expires, generate a
  new one in the Meta dashboard, paste it into `.env`, and delete the `access_token`
  row by running: `python -c "import db;c=db.connect();c.execute(\"DELETE FROM settings WHERE key='access_token'\");c.commit()"`
- **Trial reels:** the API doesn't label trial reels, so tick the **Trial** box next
  to them in the dashboard table. A comparison of trial vs regular reels then appears.
- **Delays:** Instagram's stats can lag up to 48 hours.
- **Photos:** only videos are tracked. Use `python sync.py --include-photos` to add photos.
- Data lives in `ig_analytics.db` (SQLite) on your computer only.
