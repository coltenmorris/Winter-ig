"""Manual tags (ads / sponsored posts, trial reels) kept in flags.json in the repo.

The stats database is rebuilt by the daily sync, so anything you tag by hand lives here instead.
When the app runs on Streamlit Cloud, saving also commits flags.json back to GitHub so the tag
survives redeploys and shows up on the GitHub Pages site after its next rebuild.
"""
import base64
import json
import os
from datetime import date
from pathlib import Path

import requests

FLAGS_PATH = Path(__file__).with_name("flags.json")
EMPTY = {"ads": {}, "trial": []}


def load_flags() -> dict:
    try:
        data = json.loads(FLAGS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return json.loads(json.dumps(EMPTY))
    data.setdefault("ads", {})
    data.setdefault("trial", [])
    return data


def _secret(key: str) -> str:
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, "")


def save_flags(flags: dict, message: str) -> tuple[bool, str]:
    """Write flags.json locally and, if GITHUB_TOKEN is set, commit it to the repo.
    Returns (saved_to_github, note)."""
    text = json.dumps(flags, indent=2, sort_keys=True) + "\n"
    FLAGS_PATH.write_text(text)
    token = _secret("GITHUB_TOKEN")
    repo = _secret("GITHUB_REPO") or "coltenmorris/Winter-ig"
    if not token:
        return False, ("Saved for now, but it will reset on the next redeploy. Add a GITHUB_TOKEN secret "
                       "in the app settings to keep tags permanently.")
    url = f"https://api.github.com/repos/{repo}/contents/flags.json"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        cur = requests.get(url, headers=headers, timeout=20)
        sha = cur.json().get("sha") if cur.status_code == 200 else None
        body = {"message": message, "content": base64.b64encode(text.encode()).decode(), "branch": "main"}
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=headers, json=body, timeout=20)
        if r.status_code in (200, 201):
            return True, "Saved."
        return False, f"Saved locally, but GitHub refused the update ({r.status_code}): {r.json().get('message', '')}"
    except requests.RequestException as e:
        return False, f"Saved locally, but couldn't reach GitHub: {e}"


def set_ad(flags: dict, media_id: str, is_ad: bool, brand: str = "") -> dict:
    if is_ad:
        prev = flags["ads"].get(media_id, {})
        flags["ads"][media_id] = {"brand": brand.strip(), "tagged": prev.get("tagged", date.today().isoformat())}
    else:
        flags["ads"].pop(media_id, None)
    return flags


def set_trial(flags: dict, media_id: str, is_trial: bool) -> dict:
    ids = set(flags["trial"])
    (ids.add if is_trial else ids.discard)(media_id)
    flags["trial"] = sorted(ids)
    return flags
