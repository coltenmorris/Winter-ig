# Instagram Video Analytics

A local dashboard that pulls your Instagram video stats (views, reach, likes, comments,
shares, saves, watch time, skip rate) into a database every day and charts the trends.

## 1. Install (one time)

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

## 2. Add your token

1. Copy `.env.example` to a new file named `.env`
2. Paste your Instagram access token after `IG_ACCESS_TOKEN=`
3. Save. Never share or upload `.env`.

## 3. Run it

```
python sync.py          # pulls your stats (first run takes a minute)
streamlit run app.py    # opens the dashboard in your browser
```

You can also press **Sync now** inside the dashboard.

Want to see it before connecting? `python sync.py --demo` fills it with fake data.
Delete `ig_analytics.db` afterwards to start fresh with your real stats.

## 4. Sync automatically every day

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
