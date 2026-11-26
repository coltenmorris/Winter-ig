"""Editorial media-kit layout (cover, numbered sections, stat tiles, partnerships, Insights gallery).

Laid out after the PDF media kit, in the app's own forest palette. Styles here use their own `ed-`
class names so nothing else on the site (including the live follower count) is affected.
"""
import html
import json
from datetime import date
from pathlib import Path

import streamlit as st

from shared import CANOPY, FERN, FERNB, IVY, MIST, MOSSD, RULE_C, STONE

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
STATIC_URL = "app/static/"  # Streamlit serves ./static here (enableStaticServing in .streamlit/config.toml)
esc = html.escape
PLEX = "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif"
LABEL = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def content() -> dict:
    return load_json(ROOT / "kit_content.json")


def asset(rel: str) -> str | None:
    """URL of a file in ./static, or None if it isn't there."""
    return STATIC_URL + rel if (STATIC / rel).is_file() else None


def nice_date(iso: str) -> str:
    try:
        return f"{date.fromisoformat(iso):%b %-d, %Y}"
    except (TypeError, ValueError):
        return ""


class Sections:
    """Numbers the sections in order (01 / PROFILE, 02 / PERFORMANCE, ...) and draws each one's header."""

    def __init__(self, name: str):
        self.name, self.n = name, 0

    def head(self, label: str, title: str, sub: str = "") -> str:
        self.n += 1
        return (f'<div class="ed-sec"><div class="ed-run"><span>{esc(self.name.upper())}</span><span>{esc(label.upper())}</span></div>'
                f'<div class="ed-kick">{self.n:02d} / {esc(label.upper())}</div>'
                f'<div class="ed-title">{esc(title)}</div>'
                + (f'<div class="ed-sub">{esc(sub)}</div>' if sub else "") + "</div>")


def gallery_html() -> str:
    """Original Instagram Insights screenshots, grouped by the dashboard tab they came from."""
    g = load_json(STATIC / "gallery" / "gallery.json")
    shots = [s for s in g.get("shots", []) if asset("gallery/" + s.get("file", ""))]
    if not shots:
        return ""
    cats = list(dict.fromkeys(g.get("categories", []) + [s.get("category") or "Other" for s in shots]))
    # Exhibits are numbered in the order they appear on the page, category by category
    n = 0
    for cat in cats:
        for s in shots:
            if (s.get("category") or "Other") == cat:
                n += 1
                s["n"] = n
    out = []
    for cat in cats:
        group = [s for s in shots if (s.get("category") or "Other") == cat]
        if not group:
            continue
        cards = []
        for s in group:
            url = asset("gallery/" + s["file"])
            taken, added = nice_date(s.get("taken")), nice_date(s.get("added"))
            dates = "".join(f"<span>{x}</span>" for x in (f"Taken {taken}" if taken else "", f"Added {added}" if added else "") if x)
            cards.append(
                f'<figure class="ed-shot"><a class="ed-frame" href="{esc(url)}" target="_blank" rel="noopener" '
                f'aria-label="Open exhibit {s["n"]:02d} full size"><img src="{esc(url)}" alt="Instagram Insights: '
                f'{esc(cat)}, {esc(s.get("title", ""))}" loading="lazy"></a>'
                f'<figcaption><b>Exhibit {s["n"]:02d}</b><span class="ed-shot-t">{esc(s.get("title", ""))}</span>'
                f'<span class="ed-shot-d">{dates}</span></figcaption></figure>')
        out.append(f'<div class="ed-cat"><div class="ed-cat-h"><span>{esc(cat)}</span>'
                   f'<span>{len(group)} {"screenshot" if len(group) == 1 else "screenshots"}</span></div>'
                   f'<div class="ed-shots">{"".join(cards)}</div></div>')
    return "".join(out)


def inject():
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500&display=swap');
.ed-cover {{ display:grid; grid-template-columns: 47fr 53fr; min-height: 640px; border: 1px solid {RULE_C}; }}
.ed-panel {{ background: {FERN}; padding: 44px 44px 40px; display:flex; flex-direction:column; color: {MIST}; }}
.ed-panel hr {{ border: 0; border-top: 1px solid rgba(211,219,207,.45); margin: 26px 0; width: 100%; }}
.ed-panel .ed-k {{ font: 700 .82rem/1.2 {LABEL}; letter-spacing: .02em; text-transform: uppercase; color: {MIST}; }}
.ed-name {{ font: 300 clamp(3rem, 6.6vw, 4.6rem)/1.06 {PLEX}; text-transform: uppercase; letter-spacing: .01em; margin: 34px 0 30px; color: {MIST}; }}
.ed-cats div {{ font: 700 .95rem/1.85 {LABEL}; text-transform: uppercase; color: {MIST}; opacity: .9; }}
.ed-stat {{ margin-top: 10px; }}
.ed-stat + .ed-stat {{ margin-top: 22px; }}
.ed-stat b {{ display:block; font: 400 clamp(2.4rem, 4.4vw, 3rem)/1.1 {PLEX}; letter-spacing: .01em; color: {MIST}; }}
.ed-stat span {{ display:block; margin-top: 6px; font: 700 .95rem/1.3 {LABEL}; color: {MIST}; opacity: .85; }}
.ed-panel-foot {{ margin-top: auto; padding-top: 40px; }}
.ed-panel-foot .h {{ font: 400 1.1rem/1.3 {LABEL}; color: {MIST}; }}
.ed-panel-foot .d {{ font: 400 .78rem/1.3 {LABEL}; text-transform: uppercase; margin-top: 10px; color: {MIST}; opacity: .8; }}
.ed-panel-foot .contact {{ margin-top: 22px; }}
.ed-photo {{ background: {CANOPY}; position: relative; overflow: hidden; min-height: 320px; }}
.ed-photo img {{ position:absolute; inset:0; width:100%; height:100%; object-fit: cover; display:block; }}

.ed-sec {{ margin: 5.5rem 0 1.6rem; }}
.ed-run {{ display:flex; justify-content:space-between; align-items:baseline; gap: 16px; padding-bottom: 14px;
  border-bottom: 1px solid {RULE_C}; margin-bottom: 30px; font: 700 .85rem/1 {LABEL}; color: {MIST}; }}
.ed-run span + span {{ font-weight: 400; font-size: .8rem; color: {STONE}; }}
.ed-kick {{ font: 700 .85rem/1.2 {LABEL}; color: {STONE}; text-transform: uppercase; letter-spacing: .01em; }}
.ed-title {{ font: 400 clamp(2.2rem, 5.2vw, 3.3rem)/1.08 {PLEX}; color: {MIST}; letter-spacing: .005em; margin: 18px 0 0; }}
.ed-sub {{ font: 400 .95rem/1.4 {LABEL}; color: {STONE}; margin-top: 16px; }}
.ed-label {{ font: 700 .82rem/1.2 {LABEL}; color: {STONE}; text-transform: uppercase; letter-spacing: .01em; margin: 44px 0 20px; }}
.ed-fine {{ font: 400 .8rem/1.4 {LABEL}; color: {STONE}; margin-top: 18px; }}

/* 01 profile */
.ed-profile {{ display:grid; grid-template-columns: 1fr 1.15fr; gap: 26px; align-items: start; }}
.ed-profile .ed-pimg {{ aspect-ratio: 3/4; background: {CANOPY}; overflow:hidden; }}
.ed-profile .ed-pimg img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.ed-about {{ background: {CANOPY}; border: 1px solid {RULE_C}; padding: 30px 30px 32px; }}
.ed-about h4 {{ font: 700 .9rem/1.2 {LABEL} !important; text-transform: uppercase; color: {MIST}; margin: 0 0 16px !important; padding: 0 !important; }}
.ed-about p {{ font: 400 1.02rem/1.8 {LABEL}; color: {MIST}; margin: 0 0 1.1em; }}
.ed-about p:last-child {{ margin-bottom: 0; }}
.ed-about .created {{ font: 400 .85rem/1.4 {LABEL}; color: {STONE}; margin-top: 18px; }}
.ed-pillars {{ list-style: none; padding: 0 10px; margin: 0; }}
.ed-pillars li {{ display:grid; grid-template-columns: 38px 1fr; font: 700 1.1rem/1.2 {LABEL}; text-transform: uppercase; color: {MIST}; margin: 0 0 22px; }}
.ed-pillars li span {{ color: {STONE}; }}
.ed-profile .ed-label {{ margin: 44px 10px 20px; }}

/* stat tiles */
.ed-tiles {{ display:grid; grid-template-columns: 1fr 1fr; gap: 22px; }}
.ed-tile {{ background: {CANOPY}; border: 1px solid {RULE_C}; padding: 30px 28px 28px; min-width: 0; }}
.ed-tile b {{ display:block; font: 400 clamp(2.2rem, 4.6vw, 3.1rem)/1.05 {PLEX}; color: {MIST}; letter-spacing: .01em; }}
.ed-tile > span {{ display:block; margin-top: 22px; font: 700 .85rem/1.3 {LABEL}; text-transform: uppercase; color: {STONE}; }}
.ed-tile .lm {{ text-transform: none; font-weight: 400; margin-top: 8px; }}
.ed-up {{ font-style: normal; color: #7CC47F; font-size: .75em; margin-right: 2px; }}
.ed-tile.dark {{ background: {FERN}; border-color: {FERN}; }}
.ed-tile.dark > span {{ color: {MIST}; }}
.ed-tiles.big .ed-tile {{ padding: 34px 30px 52px; }}
.ed-tiles.big .ed-tile b {{ font-size: clamp(3rem, 6.4vw, 4.4rem); }}
.ed-tiles.big .ed-tile > span {{ margin-top: 14px; font-size: .95rem; }}
.ed-band {{ height: 12px; background: {MOSSD}; margin-top: 22px; }}
.ed-signals {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }}
.ed-signals b {{ display:block; font: 400 clamp(1.8rem, 3.4vw, 2.3rem)/1.1 {PLEX}; color: {MIST}; letter-spacing: .01em; }}
.ed-signals span {{ display:block; margin-top: 22px; font: 700 .8rem/1.2 {LABEL}; text-transform: uppercase; color: {STONE}; }}

/* age bars */
.ed-bars .r {{ display:grid; grid-template-columns: 7rem 1fr 6rem; gap: 18px; align-items:center; margin: 0 0 30px; font: 400 .95rem/1 {LABEL}; color: {MIST}; }}
.ed-bars .t {{ height: 16px; background: {IVY}; }}
.ed-bars .f {{ height: 100%; background: {MOSSD}; display:block; }}
.ed-bars .p {{ text-align: right; }}
.ed-bars .chg {{ display:block; margin: 6px 0 0; font-size: .75rem; }}
.ed-countries {{ font: 400 1rem/1.8 {LABEL}; color: {MIST}; }}

/* 05 partnerships */
.ed-deal {{ display:grid; grid-template-columns: 1fr 1fr; align-items:center; gap: 20px; background: {FERN}; padding: 34px 40px; }}
.ed-deal b {{ font: 400 clamp(2.6rem, 5.4vw, 3.4rem)/1 {PLEX}; color: {MIST}; text-align: center; letter-spacing: .01em; }}
.ed-deal h4 {{ font: 700 1rem/1.3 {LABEL} !important; text-transform: uppercase; color: {MIST}; margin: 0 !important; padding: 0 !important; }}
.ed-deal p {{ font: 400 .88rem/1.4 {LABEL}; color: {MIST}; opacity: .85; margin: 12px 0 0; }}
.ed-brands {{ margin-top: 6px; }}
.ed-brand {{ display:grid; grid-template-columns: 1fr auto; align-items:center; gap: 16px; padding: 18px 10px 18px 2px; border-bottom: 1px solid {RULE_C}; }}
.ed-brand b {{ display:block; font: 700 1rem/1.3 {LABEL}; text-transform: uppercase; color: {MIST}; }}
.ed-brand span {{ display:block; font: 400 .88rem/1.3 {LABEL}; color: {STONE}; margin-top: 6px; }}
.ed-brand em {{ font: 700 1.1rem/1 {LABEL}; font-style: normal; color: {MIST}; }}

/* 06 gallery */
.ed-cat {{ margin-top: 40px; }}
.ed-cat-h {{ display:flex; justify-content:space-between; align-items:baseline; padding-bottom: 12px; margin-bottom: 22px;
  border-bottom: 1px solid {RULE_C}; font: 700 .9rem/1 {LABEL}; text-transform: uppercase; color: {MIST}; }}
.ed-cat-h span + span {{ font-weight: 400; font-size: .8rem; text-transform: none; color: {STONE}; }}
.ed-shots {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 26px 22px; align-items: start; }}
.ed-shot {{ margin: 0; min-width: 0; }}
.ed-frame {{ display:block; background: {CANOPY}; border: 1px solid {RULE_C}; padding: 12px; }}
.ed-frame:hover {{ border-color: {FERNB}; }}
.ed-frame img {{ display:block; width:100%; height:auto; }}
.ed-shot figcaption {{ margin-top: 12px; font: 400 .85rem/1.35 {LABEL}; color: {STONE}; }}
.ed-shot figcaption b {{ display:block; font-weight: 700; text-transform: uppercase; color: {STONE}; font-size: .8rem; }}
.ed-shot-t {{ display:block; color: {MIST}; margin-top: 4px; }}
.ed-shot-d {{ display:block; margin-top: 4px; font-size: .78rem; }}
.ed-shot-d span {{ display:block; }}

.ed-foot {{ display:flex; justify-content:space-between; gap: 16px; flex-wrap: wrap; margin-top: 4.5rem; padding-top: 14px;
  border-top: 1px solid {RULE_C}; font: 400 .78rem/1.4 {LABEL}; color: {STONE}; }}
.ed-foot span:first-child {{ text-transform: uppercase; }}

@media (max-width: 900px) {{ .ed-shots {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 760px) {{
  .ed-cover {{ grid-template-columns: 1fr; min-height: 0; }}
  .ed-photo {{ order: -1; aspect-ratio: 4/5; }}
  .ed-panel {{ padding: 32px 24px; }}
  .ed-profile, .ed-tiles, .ed-deal {{ grid-template-columns: 1fr; }}
  .ed-signals {{ grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 28px; }}
  .ed-shots {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px 14px; }}
  .ed-bars .r {{ grid-template-columns: 4rem 1fr 4.6rem; gap: 12px; }}
  .ed-deal {{ padding: 28px 24px; }}
  .ed-deal b {{ text-align: left; }}
  .ed-sec {{ margin-top: 4rem; }}
}}
</style>""", unsafe_allow_html=True)
