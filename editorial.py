"""Editorial media-kit layout (cover, numbered sections, stat tiles, partnerships, Insights gallery).

Laid out after the PDF media kit, in the app's own forest palette. Styles here use their own `ed-`
class names so nothing else on the site (including the live follower count) is affected.
"""
import html
import json
from datetime import date
from pathlib import Path

import streamlit as st

from shared import FERNB, MIST, STONE

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
STATIC_URL = "app/static/"  # Streamlit serves ./static here (enableStaticServing in .streamlit/config.toml)
esc = html.escape
# Apple's system font (SF Pro) on Apple devices, Inter everywhere else
PLEX = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', 'Helvetica Neue', Arial, sans-serif"
LABEL = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Helvetica Neue', Arial, sans-serif"


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


# ---------------- Liquid Glass styling ----------------
# Translucent panels that blur and tint whatever is behind them (the moving background, the cover photo),
# with a bright rim on the top edge, a soft inner glow and deep rounded corners. Forest palette throughout.
GLASS_BG = "linear-gradient(160deg, rgba(211,219,207,.13) 0%, rgba(211,219,207,.05) 45%, rgba(143,175,120,.07) 100%)"
TINT_BG = "linear-gradient(160deg, rgba(143,175,120,.34) 0%, rgba(46,64,48,.55) 55%, rgba(46,64,48,.68) 100%)"
RIM = ("inset 0 1px 0 rgba(255,255,255,.30), inset 0 -1px 0 rgba(255,255,255,.06), "
       "inset 0 0 0 1px rgba(255,255,255,.07), 0 18px 44px -18px rgba(0,0,0,.55)")
BLUR = "blur(26px) saturate(170%)"


def _glass(sel: str, radius: int, tint: bool = False) -> str:
    return (f"{sel} {{ position: relative; isolation: isolate; border-radius: {radius}px; background: {TINT_BG if tint else GLASS_BG};"
            f" -webkit-backdrop-filter: {BLUR}; backdrop-filter: {BLUR}; box-shadow: {RIM}; border: 0 !important; }}"
            # specular sheen across the top-left of the glass
            f"{sel}::before {{ content: ''; position: absolute; inset: 0; border-radius: inherit; pointer-events: none; z-index: -1;"
            f" background: radial-gradient(120% 70% at 12% -10%, rgba(255,255,255,.16), transparent 55%); }}")


def inject():
    glass = "".join([
        _glass(".ed-panel", 30, tint=True), _glass(".ed-run", 999), _glass(".ed-about", 28),
        _glass(".ed-tile", 28), _glass(".ed-tile.dark", 28, tint=True), _glass(".ed-signals", 28),
        _glass(".ed-deal", 28, tint=True), _glass(".ed-brands", 28), _glass(".ed-frame", 30),
        _glass(".ed-cat-h", 999), _glass(".ed-foot", 999), _glass(".ed-pillars", 28),
        _glass(".ed-reels .reel .card", 22), _glass(".ed-bars", 28), _glass(".ed-countries", 28),
    ])
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
{glass}
/* cover: the photo sits behind a floating glass panel that blurs its edge */
.ed-cover {{ position: relative; display:grid; grid-template-columns: 47fr 53fr; min-height: 660px; border-radius: 38px; overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.10), 0 30px 70px -30px rgba(0,0,0,.7); }}
.ed-photo {{ position: absolute; inset: 0; overflow: hidden; z-index: 0; }}
.ed-photo img {{ width:100%; height:100%; object-fit: cover; object-position: 70% 48%; display:block; }}
.ed-panel {{ z-index: 1; margin: 16px; padding: 40px 40px 36px; display:flex; flex-direction:column; color: {MIST}; }}
.ed-panel hr {{ border: 0; height: 1px; background: linear-gradient(90deg, rgba(255,255,255,.4), rgba(255,255,255,.05)); margin: 24px 0; width: 100%; }}
.ed-panel .ed-k {{ font: 600 .78rem/1.2 {LABEL}; letter-spacing: .08em; text-transform: uppercase; color: {MIST}; opacity: .85; }}
.ed-name {{ font: 600 clamp(3rem, 6.4vw, 4.5rem)/1.02 {PLEX}; text-transform: uppercase; letter-spacing: -.025em; margin: 30px 0 26px; color: #fff; }}
.ed-cats div {{ font: 600 .9rem/1.8 {LABEL}; letter-spacing: .04em; text-transform: uppercase; color: {MIST}; opacity: .9; }}
.ed-stat {{ margin-top: 8px; }}
.ed-stat + .ed-stat {{ margin-top: 20px; }}
.ed-stat b {{ display:block; font: 600 clamp(2.4rem, 4.4vw, 3rem)/1.08 {PLEX}; letter-spacing: -.03em; color: #fff; }}
.ed-stat span {{ display:block; margin-top: 4px; font: 500 .92rem/1.3 {LABEL}; color: {MIST}; opacity: .8; }}
.ed-panel-foot {{ margin-top: auto; padding-top: 36px; }}
.ed-panel-foot .h {{ font: 600 1.08rem/1.3 {LABEL}; color: #fff; }}
.ed-panel-foot .d {{ font: 500 .74rem/1.3 {LABEL}; letter-spacing: .08em; text-transform: uppercase; margin-top: 8px; color: {MIST}; opacity: .75; }}
.ed-panel-foot .contact {{ margin-top: 20px; border-radius: 999px; padding: 11px 22px; background: rgba(255,255,255,.88); color: #0E1411 !important;
  box-shadow: inset 0 1px 0 #fff, 0 8px 20px -8px rgba(0,0,0,.5); }}

/* section headers: a floating glass capsule, then the title */
.ed-sec {{ margin: 5.5rem 0 1.6rem; }}
.ed-run {{ display:flex; justify-content:space-between; align-items:center; gap: 16px; padding: 13px 22px; margin-bottom: 30px;
  font: 600 .8rem/1 {LABEL}; letter-spacing: .04em; color: {MIST}; }}
.ed-run span + span {{ font-weight: 500; color: {STONE}; }}
.ed-kick {{ font: 600 .8rem/1.2 {LABEL}; color: {FERNB}; text-transform: uppercase; letter-spacing: .08em; }}
.ed-title {{ font: 700 clamp(2.2rem, 5.2vw, 3.4rem)/1.05 {PLEX}; color: #fff; letter-spacing: -.035em; margin: 14px 0 0; }}
.ed-sub {{ font: 400 1rem/1.45 {LABEL}; color: {STONE}; margin-top: 12px; }}
.ed-label {{ font: 600 .78rem/1.2 {LABEL}; color: {STONE}; text-transform: uppercase; letter-spacing: .08em; margin: 40px 0 16px 6px; }}
.ed-fine {{ font: 400 .82rem/1.45 {LABEL}; color: {STONE}; margin: 16px 6px 0; }}

/* 01 profile */
.ed-profile {{ display:grid; grid-template-columns: 1fr 1.15fr; gap: 22px; align-items: start; }}
.ed-profile .ed-pimg {{ aspect-ratio: 3/4; overflow:hidden; border-radius: 30px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.12), 0 24px 50px -24px rgba(0,0,0,.7); }}
.ed-profile .ed-pimg img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.ed-about {{ padding: 28px 30px 30px; }}
.ed-about h4 {{ font: 600 .8rem/1.2 {LABEL} !important; letter-spacing: .08em; text-transform: uppercase; color: {FERNB}; margin: 0 0 14px !important; padding: 0 !important; }}
.ed-about p {{ font: 400 1.05rem/1.7 {LABEL}; color: {MIST}; margin: 0 0 1em; }}
.ed-about p:last-child {{ margin-bottom: 0; }}
.ed-about .created {{ font: 500 .82rem/1.4 {LABEL}; color: {STONE}; margin-top: 16px; }}
.ed-pillars {{ list-style: none; padding: 10px 24px; margin: 0; }}
.ed-pillars li {{ display:grid; grid-template-columns: 38px 1fr; align-items:center; font: 600 1.05rem/1.2 {LABEL}; letter-spacing: .02em;
  text-transform: uppercase; color: #fff; padding: 14px 0; }}
.ed-pillars li + li {{ border-top: 1px solid rgba(255,255,255,.08); }}
.ed-pillars li span {{ display:inline-flex; align-items:center; justify-content:center; width: 26px; height: 26px; border-radius: 50%;
  font-size: .78rem; color: {MIST}; background: rgba(255,255,255,.10); box-shadow: inset 0 1px 0 rgba(255,255,255,.25); }}
.ed-profile .ed-label {{ margin: 28px 6px 12px; }}

/* stat tiles */
.ed-tiles {{ display:grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
.ed-tile {{ padding: 28px 28px 26px; min-width: 0; }}
.ed-tile b {{ display:block; font: 600 clamp(2.2rem, 4.6vw, 3.1rem)/1.05 {PLEX}; color: #fff; letter-spacing: -.035em; }}
.ed-tile > span {{ display:block; margin-top: 16px; font: 600 .78rem/1.3 {LABEL}; letter-spacing: .07em; text-transform: uppercase; color: {STONE}; }}
.ed-tile .lm {{ text-transform: none; font: 400 .85rem/1.3 {LABEL}; margin-top: 8px; color: {STONE}; }}
.ed-up {{ font-style: normal; color: #7CC47F; font-size: .75em; margin-right: 2px; }}
.ed-tile.dark > span {{ color: {MIST}; }}
.ed-tiles.big .ed-tile {{ padding: 32px 30px 44px; }}
.ed-tiles.big .ed-tile b {{ font-size: clamp(3rem, 6.4vw, 4.4rem); }}
.ed-tiles.big .ed-tile > span {{ margin-top: 10px; font-size: .85rem; }}
.ed-band {{ height: 10px; border-radius: 999px; margin-top: 18px;
  background: linear-gradient(90deg, rgba(143,175,120,.85), rgba(143,175,120,.35)); box-shadow: inset 0 1px 0 rgba(255,255,255,.35), 0 6px 18px -6px rgba(143,175,120,.5); }}
.ed-signals {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; padding: 8px 0; }}
.ed-signals > div {{ padding: 20px 26px; }}
.ed-signals > div + div {{ border-left: 1px solid rgba(255,255,255,.08); }}
.ed-signals b {{ display:block; font: 600 clamp(1.8rem, 3.4vw, 2.3rem)/1.1 {PLEX}; color: #fff; letter-spacing: -.03em; }}
.ed-signals span {{ display:block; margin-top: 10px; font: 600 .74rem/1.2 {LABEL}; letter-spacing: .07em; text-transform: uppercase; color: {STONE}; }}

/* age bars: glossy capsules */
.ed-bars {{ padding: 26px 28px 4px; }}
.ed-bars .r {{ display:grid; grid-template-columns: 6rem 1fr 6rem; gap: 18px; align-items:center; margin: 0 0 22px; font: 500 .95rem/1 {LABEL}; color: {MIST}; }}
.ed-bars .t {{ height: 14px; border-radius: 999px; background: rgba(255,255,255,.07); box-shadow: inset 0 1px 2px rgba(0,0,0,.35); overflow: hidden; }}
.ed-bars .f {{ height: 100%; display:block; border-radius: 999px; background: linear-gradient(180deg, #A9C795, {FERNB} 55%, #6E8F5C);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.45); }}
.ed-bars .p {{ text-align: right; font-weight: 600; }}
.ed-bars .chg {{ display:block; margin: 6px 0 0; font-size: .75rem; font-weight: 400; }}
.ed-countries {{ font: 500 1rem/1.9 {LABEL}; color: {MIST}; padding: 18px 26px; }}

/* 05 partnerships */
.ed-deal {{ display:grid; grid-template-columns: 1fr 1fr; align-items:center; gap: 20px; padding: 34px 40px; }}
.ed-deal b {{ font: 600 clamp(2.6rem, 5.4vw, 3.6rem)/1 {PLEX}; color: #fff; text-align: center; letter-spacing: -.035em; }}
.ed-deal h4 {{ font: 600 .85rem/1.3 {LABEL} !important; letter-spacing: .07em; text-transform: uppercase; color: #fff; margin: 0 !important; padding: 0 !important; }}
.ed-deal p {{ font: 400 .9rem/1.4 {LABEL}; color: {MIST}; opacity: .85; margin: 10px 0 0; }}
.ed-brands {{ margin-top: 14px; padding: 4px 26px; }}
.ed-brand {{ display:grid; grid-template-columns: 1fr auto; align-items:center; gap: 16px; padding: 18px 0; }}
.ed-brand + .ed-brand {{ border-top: 1px solid rgba(255,255,255,.08); }}
.ed-brand b {{ display:block; font: 600 .98rem/1.3 {LABEL}; letter-spacing: .03em; text-transform: uppercase; color: #fff; }}
.ed-brand span {{ display:block; font: 400 .88rem/1.3 {LABEL}; color: {STONE}; margin-top: 4px; }}
.ed-brand em {{ font: 600 1.05rem/1 {LABEL}; font-style: normal; color: #fff; padding: 8px 14px; border-radius: 999px;
  background: rgba(255,255,255,.08); box-shadow: inset 0 1px 0 rgba(255,255,255,.2); }}

/* 06 gallery */
.ed-cat {{ margin-top: 34px; }}
.ed-cat-h {{ display:flex; justify-content:space-between; align-items:center; padding: 12px 22px; margin-bottom: 20px;
  font: 600 .82rem/1 {LABEL}; letter-spacing: .07em; text-transform: uppercase; color: #fff; }}
.ed-cat-h span + span {{ font-weight: 500; letter-spacing: 0; text-transform: none; color: {STONE}; }}
.ed-shots {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 26px 20px; align-items: start; }}
.ed-shot {{ margin: 0; min-width: 0; }}
.ed-frame {{ display:block; padding: 10px; transition: transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .25s; }}
.ed-frame:hover {{ transform: translateY(-3px) scale(1.012); }}
.ed-frame img {{ display:block; width:100%; height:auto; border-radius: 22px; }}
.ed-shot figcaption {{ margin: 12px 8px 0; font: 400 .85rem/1.35 {LABEL}; color: {STONE}; }}
.ed-shot figcaption b {{ display:block; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: {FERNB}; font-size: .74rem; }}
.ed-shot-t {{ display:block; color: #fff; font-weight: 500; margin-top: 4px; }}
.ed-shot-d {{ display:block; margin-top: 4px; font-size: .78rem; }}
.ed-shot-d span {{ display:block; }}

/* top reels on the media kit */
.ed-reels .reel .thumb {{ border-radius: 26px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.12), 0 20px 40px -22px rgba(0,0,0,.7); }}
.ed-reels .reel .best {{ top: 12px; left: 12px; border-radius: 999px; padding: 6px 12px; background: rgba(230,212,156,.9);
  -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px); box-shadow: inset 0 1px 0 rgba(255,255,255,.6); }}
.ed-reels .reel .card {{ margin-top: 10px; padding: 4px 16px 14px; }}

/* segmented switches on the media kit: glass capsules (the live-count switch is left alone) */
.st-key-win [data-testid="stButtonGroup"], .st-key-aud [data-testid="stButtonGroup"], .st-key-top_range [data-testid="stButtonGroup"] {{
  display: inline-flex; gap: 2px; padding: 4px; border-radius: 999px; background: {GLASS_BG};
  -webkit-backdrop-filter: {BLUR}; backdrop-filter: {BLUR}; box-shadow: {RIM}; }}
.st-key-win button, .st-key-aud button, .st-key-top_range button {{ border-radius: 999px !important; border: 0 !important;
  background: transparent !important; color: {MIST} !important; padding: 6px 16px !important; font-family: {LABEL} !important; }}
.st-key-win button[aria-checked="true"], .st-key-aud button[aria-checked="true"], .st-key-top_range button[aria-checked="true"] {{
  background: rgba(255,255,255,.88) !important; color: #0E1411 !important; box-shadow: inset 0 1px 0 #fff, 0 4px 12px -4px rgba(0,0,0,.5); }}
.st-key-win button[aria-checked="true"] *, .st-key-aud button[aria-checked="true"] *, .st-key-top_range button[aria-checked="true"] * {{ color: #0E1411 !important; }}

.ed-foot {{ display:flex; justify-content:space-between; gap: 16px; flex-wrap: wrap; margin-top: 4.5rem; padding: 14px 24px;
  font: 400 .78rem/1.4 {LABEL}; color: {STONE}; }}
.ed-foot span:first-child {{ text-transform: uppercase; letter-spacing: .06em; font-weight: 600; color: {MIST}; }}

/* where blur isn't available, or the viewer asked for less transparency, use solid panels */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {{
  .ed-run, .ed-about, .ed-tile, .ed-signals, .ed-brands, .ed-frame, .ed-cat-h, .ed-foot, .ed-pillars, .ed-bars, .ed-countries,
  .ed-reels .reel .card {{ background: #18221B; }}
  .ed-panel, .ed-tile.dark, .ed-deal {{ background: #2E4030; }} }}
@media (prefers-reduced-transparency: reduce) {{
  .ed-run, .ed-about, .ed-tile, .ed-signals, .ed-brands, .ed-frame, .ed-cat-h, .ed-foot, .ed-pillars, .ed-bars, .ed-countries,
  .ed-reels .reel .card {{ background: #18221B; backdrop-filter: none; -webkit-backdrop-filter: none; }}
  .ed-panel, .ed-tile.dark, .ed-deal {{ background: #2E4030; backdrop-filter: none; -webkit-backdrop-filter: none; }} }}
@media (prefers-reduced-motion: reduce) {{ .ed-frame {{ transition: none; }} .ed-frame:hover {{ transform: none; }} }}

@media (max-width: 900px) {{ .ed-shots {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 760px) {{
  .ed-cover {{ display:flex; flex-direction: column; min-height: 0; border-radius: 30px; }}
  .ed-photo {{ position: relative; inset: auto; aspect-ratio: 4/5; order: -1; flex: none; }}
  .ed-panel {{ margin: -110px 10px 10px; padding: 30px 24px; }}
  .ed-profile, .ed-tiles, .ed-deal {{ grid-template-columns: 1fr; }}
  .ed-signals {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .ed-signals > div:nth-child(3) {{ border-left: 0; }}
  .ed-signals > div:nth-child(n+3) {{ border-top: 1px solid rgba(255,255,255,.08); }}
  .ed-shots {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px 12px; }}
  .ed-bars {{ padding: 22px 18px 2px; }}
  .ed-bars .r {{ grid-template-columns: 3.6rem 1fr 4.4rem; gap: 12px; }}
  .ed-deal {{ padding: 28px 24px; }}
  .ed-deal b {{ text-align: left; }}
  .ed-brands {{ padding: 4px 18px; }}
  .ed-sec {{ margin-top: 4rem; }}
}}
</style>""", unsafe_allow_html=True)
