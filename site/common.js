// Shared helpers for both pages. Data comes from data.js (window.DATA), rebuilt daily.
const D = window.DATA;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => {
  if (n === null || n === undefined || Number.isNaN(n)) return "n/a";
  const a = Math.abs(n);
  if (a >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  if (a >= 1e4) return Math.round(n / 1e3) + "K";
  if (a >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "K";
  return Math.round(n).toLocaleString();
};
const pct = n => (n === null || n === undefined) ? "n/a" : (n * 100).toFixed(1) + "%";
const dt = s => new Date(s);
const fmtDate = (s, o) => dt(s).toLocaleDateString("en-US", o || { month: "short", day: "numeric" });
const fmtTime = s => dt(s).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

// Views are the main measure; if Instagram hasn't returned views yet, fall back to likes.
const HAS_VIEWS = D.reels.some(r => r.total && r.total.views != null);
const MAIN = HAS_VIEWS ? "views" : "likes";
const MAIN_LABEL = HAS_VIEWS ? "views" : "likes";
const val = (r, k = MAIN) => (r.total && r.total[k] != null) ? r.total[k] : null;

const thumb = (r, badge = "") =>
  `<div class="thumb">${r.thumb ? `<img src="${esc(r.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}${badge}</div>`;

function mark(nav) {
  document.querySelectorAll("nav.top a").forEach(a => { if (a.dataset.p === nav) a.setAttribute("aria-current", "page"); });
}

// ---------- small SVG charts ----------
function lineChart(points, { w = 520, h = 200, area = true } = {}) {
  if (points.length < 2) return `<p class="lede">Trends appear after a few daily syncs.</p>`;
  const pad = { l: 40, r: 10, t: 10, b: 24 };
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys) * 0.98, y1 = Math.max(...ys) * 1.02 || 1;
  const X = x => pad.l + (x - x0) / ((x1 - x0) || 1) * (w - pad.l - pad.r);
  const Y = y => h - pad.b - (y - y0) / ((y1 - y0) || 1) * (h - pad.t - pad.b);
  const d = points.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
  const grid = [0, .5, 1].map(f => { const v = y0 + f * (y1 - y0); return `<line x1="${pad.l}" x2="${w - pad.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="rgba(255,252,245,.9)"/><text x="${pad.l - 6}" y="${Y(v) + 4}" text-anchor="end">${fmt(v)}</text>`; }).join("");
  const fill = area ? `<path d="${d}L${X(x1)},${h - pad.b}L${X(x0)},${h - pad.b}Z" fill="rgba(79,93,67,.14)"/>` : "";
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img">${grid}${fill}<path d="${d}" fill="none" stroke="#4F5D43" stroke-width="2.2"/>
    ${points.map(p => `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="2.6" fill="#4F5D43"/>`).join("")}</svg>`;
}

// ---------- reel detail ----------
const MS = [["views", "Views"], ["reach", "Accounts reached"], ["likes", "Likes"], ["comments", "Comments"],
  ["shares", "Shares"], ["saved", "Saves"], ["engagement", "Engagement rate"], ["watch_s", "Avg watch time"]];

function cell(s, k) {
  if (!s) return `<span class="na">not captured</span>`;
  const v = s[k];
  if (v === null || v === undefined) return `<span class="na">n/a</span>`;
  if (k === "engagement") return pct(v);
  if (k === "watch_s") return v.toFixed(1) + "s";
  return fmt(v);
}

function openReel(id) {
  const r = D.reels.find(x => x.id === id);
  if (!r) return;
  let dlg = document.getElementById("reel");
  if (!dlg) {
    dlg = document.createElement("dialog"); dlg.id = "reel"; document.body.appendChild(dlg);
    dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
  }
  const rows = MS.map(([k, l]) => `<tr><th>${l}</th><td>${cell(r.h24, k)}</td><td>${cell(r.week, k)}</td><td>${cell(r.total, k)}</td></tr>`).join("");
  dlg.innerHTML = `<button class="close" onclick="this.closest('dialog').close()">Close</button>
  <div class="mbody">
    <div class="mhead">${thumb(r)}<div>
      <div class="na" style="font-size:.9rem">${fmtDate(r.posted, { weekday: "long", month: "long", day: "numeric", year: "numeric" })} at ${fmtTime(r.posted)}${r.trial ? ", trial reel" : ""}</div>
      <div class="cap">${esc(r.caption || "No caption")}</div>
      ${r.link ? `<a href="${esc(r.link)}" target="_blank" rel="noopener">Open on Instagram</a>` : ""}
    </div></div>
    <table class="ms"><thead><tr><th></th><th>First 24 hours</th><th>First week</th><th>To date</th></tr></thead><tbody>${rows}</tbody></table>
    <p class="note">Each column uses the daily sync closest to that mark. "Not captured" means the reel was posted before
      daily tracking began, or that mark hasn't arrived yet.</p>
    ${r.series.length > 1 ? `<h3 style="margin-top:18px">${HAS_VIEWS ? "Views" : "Likes"} since posting</h3>` + lineChart(r.series, { h: 170 }) : ""}
  </div>`;
  dlg.showModal();
}
