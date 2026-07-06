"""Generate a zero-dependency static web app from waze_vps.json.

Mirrors the approach of ``readme_generator.py``: pure Python standard library,
no third-party packages, no build tooling. Reads the canonical voicepack data
and writes a single self-contained ``docs/index.html`` with the data and a tiny
inlined QR-code encoder (``qr.js``) embedded, so the page works both from
``file://`` and any static host with no runtime dependencies.

Re-run this whenever ``waze_vps.json`` changes:

    python helper_files/site_generator.py
"""

import json
import os

# Same URI scheme used by readme_generator.py
SHARE_BASE_URI = "https://waze.com/ul?acvp="
FILES_BASE_URI = "https://voice-prompts-ipv6.waze.com/"
FILES_URI_SUFFIX = ".tar.gz"

_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_here)
DATA_PATH = os.path.join(_here, "waze_vps.json")
QR_JS_PATH = os.path.join(_here, "qr.js")
OUTPUT_PATH = os.path.join(_repo_root, "docs", "index.html")


def _clean(value):
    """Return a trimmed string, or '' for missing/None values."""
    return (value or "").strip() if isinstance(value, str) else ""


def build_records(waze_vps: dict) -> list:
    """Flatten the JSON into a list of records the front-end can render."""
    records = []
    category_map = {
        "Official Voicepacks": "Official",
        "Community Voicepacks": "Community",
    }
    for json_key, category in category_map.items():
        for vp in waze_vps.get(json_key, []):
            uuid = _clean(vp.get("uuid"))
            if not uuid:
                # No uuid means there's no shareable link — skip it.
                continue
            author = _clean(vp.get("author"))
            author2 = _clean(vp.get("author_2"))
            authors = ", ".join(a for a in (author, author2) if a)
            records.append({
                "name": _clean(vp.get("name")) or "(unnamed)",
                "language": _clean(vp.get("language")) or "Unknown",
                "category": category,
                "install": SHARE_BASE_URI + uuid,
                "mp3": FILES_BASE_URI + uuid + FILES_URI_SUFFIX,
                "notes": _clean(vp.get("notes")),
                "blog": _clean(vp.get("blog")),
                "author": authors,
                "author_link": _clean(vp.get("author_link")),
            })
    records.sort(key=lambda r: r["name"].lower())
    return records


# ---------------------------------------------------------------------------
# HTML template. Uses the sentinels __QRJS__ and __DATA__ (str.replace, not
# str.format) so the CSS/JS braces can stay single and the embedded JS/JSON —
# which contain many { } — pass through untouched. All CSS/JS is inline.
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Waze Voicepack Links</title>
<style>
  :root {
    --bg: #f7f8fa; --card: #ffffff; --text: #1a1d21; --muted: #6b7280;
    --border: #e5e7eb; --accent: #33ccff; --accent-ink: #05384a;
    --chip: #eef2f6; --shadow: 0 1px 2px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.04);
    --overlay: rgba(10,14,20,.55);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0e1116; --card: #171b21; --text: #e6e8eb; --muted: #9aa4b2;
      --border: #262c36; --accent: #33ccff; --accent-ink: #04222e;
      --chip: #222833; --shadow: 0 1px 2px rgba(0,0,0,.4); --overlay: rgba(0,0,0,.66);
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  header { padding: 28px 20px 8px; max-width: 1100px; margin: 0 auto; }
  h1 { margin: 0 0 4px; font-size: 26px; }
  .tagline { color: var(--muted); margin: 0 0 20px; }
  .controls { position: sticky; top: 0; z-index: 5; background: var(--bg);
    padding: 12px 20px; border-bottom: 1px solid var(--border); }
  .controls-inner { max-width: 1100px; margin: 0 auto; display: flex; flex-wrap: wrap;
    gap: 10px; align-items: center; }
  input[type=search], select { font: inherit; color: var(--text); background: var(--card);
    border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; }
  input[type=search] { flex: 1 1 240px; min-width: 0; }
  input[type=search]:focus, select:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .seg { display: inline-flex; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
  .seg button { font: inherit; border: 0; background: var(--card); color: var(--text);
    padding: 9px 14px; cursor: pointer; }
  .seg button[aria-pressed=true] { background: var(--accent); color: var(--accent-ink); font-weight: 600; }
  .count { color: var(--muted); margin-left: auto; font-size: 14px; white-space: nowrap; }
  main { max-width: 1100px; margin: 0 auto; padding: 18px 20px 60px; }
  .grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 16px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 10px; }
  .card h2 { margin: 0; font-size: 17px; line-height: 1.3; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { font-size: 12px; padding: 3px 9px; border-radius: 999px; background: var(--chip); color: var(--muted); }
  .chip.cat-Official { background: rgba(51,204,255,.18); color: var(--accent-ink); }
  @media (prefers-color-scheme: dark) { .chip.cat-Official { color: #9fe4ff; } }
  .chip a { color: inherit; text-decoration: none; }
  .notes { color: var(--muted); font-size: 13px; margin: 0; }
  .actions { display: flex; gap: 8px; margin-top: auto; padding-top: 4px; }
  .actions a, .actions button { flex: 1; text-align: center; text-decoration: none; font: inherit;
    font-size: 14px; padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border); cursor: pointer; }
  .btn-install { background: var(--accent); color: var(--accent-ink); border-color: transparent; font-weight: 600; }
  .btn-mp3 { background: transparent; color: var(--text); }
  .empty { text-align: center; color: var(--muted); padding: 60px 20px; }
  a.author { color: var(--muted); }
  footer { max-width: 1100px; margin: 0 auto; padding: 0 20px 40px; color: var(--muted); font-size: 13px; }
  footer a { color: inherit; }
  .modal { position: fixed; inset: 0; background: var(--overlay); display: flex;
    align-items: center; justify-content: center; padding: 20px; z-index: 50; }
  .modal[hidden] { display: none; }
  .modal-box { background: var(--card); border-radius: 16px; padding: 22px; max-width: 340px; width: 100%;
    text-align: center; position: relative; box-shadow: 0 20px 60px rgba(0,0,0,.35); }
  .modal-box h3 { margin: 0 6px 14px; font-size: 18px; }
  .modal-close { position: absolute; top: 10px; right: 12px; border: 0; background: transparent;
    color: var(--muted); font-size: 24px; line-height: 1; cursor: pointer; }
  #mqr { width: 220px; height: 220px; image-rendering: pixelated; border-radius: 8px;
    background: #fff; padding: 10px; }
  .modal .notes { margin: 12px 0; }
  .modal-actions { display: flex; gap: 8px; }
  .modal-actions a, .modal-actions button { flex: 1; font: inherit; font-size: 14px; padding: 9px 10px;
    border-radius: 10px; border: 1px solid var(--border); cursor: pointer; text-decoration: none; }
  .toast { margin-top: 10px; color: var(--accent-ink); background: rgba(51,204,255,.22);
    border-radius: 8px; padding: 6px; font-size: 13px; }
  @media (prefers-color-scheme: dark) { .toast { color: #9fe4ff; } }
</style>
</head>
<body>
<header>
  <h1>🚗 Waze Voicepack Links</h1>
  <p class="tagline">A community archive of classic &amp; custom Waze GPS voices. On your phone (with Waze installed) tap <strong>Install</strong>; on desktop, tap it for a scannable QR code.</p>
</header>
<div class="controls">
  <div class="controls-inner">
    <input type="search" id="q" placeholder="Search by name…" autocomplete="off" aria-label="Search by name">
    <div class="seg" id="cat" role="group" aria-label="Category">
      <button data-cat="all" aria-pressed="true">All</button>
      <button data-cat="Official" aria-pressed="false">Official</button>
      <button data-cat="Community" aria-pressed="false">Community</button>
    </div>
    <select id="lang" aria-label="Filter by language"></select>
    <span class="count" id="count"></span>
  </div>
</div>
<main>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" hidden>No voicepacks match your filters.</div>
</main>
<footer>
  Generated from <code>waze_vps.json</code> · <span id="total"></span> voicepacks ·
  <a href="https://github.com/pipeeeeees/waze-voicepack-links">source project</a>
</footer>

<div class="modal" id="modal" hidden role="dialog" aria-modal="true" aria-labelledby="mtitle">
  <div class="modal-box">
    <button class="modal-close" id="mclose" aria-label="Close">&times;</button>
    <h3 id="mtitle"></h3>
    <canvas id="mqr" width="220" height="220"></canvas>
    <p class="notes">Scan with your phone's camera (Waze installed), or copy the link.</p>
    <div class="modal-actions">
      <a id="mopen" class="btn-install" href="#">Open in Waze</a>
      <button id="mcopy" class="btn-mp3">Copy link</button>
    </div>
    <div class="toast" id="mtoast" hidden>Link copied</div>
  </div>
</div>

<script>__QRJS__</script>
<script id="data" type="application/json">__DATA__</script>
<script>
  const DATA = JSON.parse(document.getElementById("data").textContent);
  const grid = document.getElementById("grid");
  const empty = document.getElementById("empty");
  const countEl = document.getElementById("count");
  const qEl = document.getElementById("q");
  const langEl = document.getElementById("lang");
  const catGroup = document.getElementById("cat");
  document.getElementById("total").textContent = DATA.length;

  let state = { q: "", cat: "all", lang: "all" };

  const langs = Array.from(new Set(DATA.map(d => d.language))).sort((a, b) => a.localeCompare(b));
  langEl.innerHTML = '<option value="all">All languages</option>' +
    langs.map(l => `<option value="${esc(l)}">${esc(l)}</option>`).join("");

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function render() {
    const q = state.q.trim().toLowerCase();
    const rows = DATA.filter(d =>
      (state.cat === "all" || d.category === state.cat) &&
      (state.lang === "all" || d.language === state.lang) &&
      (q === "" || d.name.toLowerCase().includes(q)));
    countEl.textContent = rows.length + (rows.length === 1 ? " voicepack" : " voicepacks");
    empty.hidden = rows.length !== 0;
    grid.innerHTML = rows.map(cardHTML).join("");
  }

  function cardHTML(d) {
    const notes = d.notes ? `<p class="notes">${esc(d.notes)}</p>` : "";
    const author = d.author
      ? `<p class="notes">by ${d.author_link
          ? `<a class="author" href="${esc(d.author_link)}" target="_blank" rel="noopener">${esc(d.author)}</a>`
          : esc(d.author)}</p>` : "";
    const blog = d.blog ? `<span class="chip"><a href="${esc(d.blog)}" target="_blank" rel="noopener">blog ↗</a></span>` : "";
    return `<article class="card">
      <h2>${esc(d.name)}</h2>
      <div class="chips">
        <span class="chip cat-${esc(d.category)}">${esc(d.category)}</span>
        <span class="chip">${esc(d.language)}</span>${blog}
      </div>
      ${notes}${author}
      <div class="actions">
        <a class="btn-install" href="${esc(d.install)}" data-install="${esc(d.install)}" data-name="${esc(d.name)}">Install</a>
        <a class="btn-mp3" href="${esc(d.mp3)}">mp3 files</a>
      </div>
    </article>`;
  }

  // --- Install: navigate on mobile, show QR + copy on desktop ---
  const isMobile = window.matchMedia("(hover: none) and (pointer: coarse)").matches;
  const modal = document.getElementById("modal");
  const mqr = document.getElementById("mqr");
  const mtitle = document.getElementById("mtitle");
  const mopen = document.getElementById("mopen");
  const mcopy = document.getElementById("mcopy");
  const mtoast = document.getElementById("mtoast");
  let currentUrl = "";

  function drawQR(text) {
    const m = QR.generate(text);
    const n = m.length, quiet = 4, scale = 6, dim = (n + quiet * 2) * scale;
    mqr.width = dim; mqr.height = dim;
    const ctx = mqr.getContext("2d");
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, dim, dim);
    ctx.fillStyle = "#000";
    for (let r = 0; r < n; r++)
      for (let c = 0; c < n; c++)
        if (m[r][c]) ctx.fillRect((c + quiet) * scale, (r + quiet) * scale, scale, scale);
  }

  function openModal(url, name) {
    currentUrl = url;
    mtitle.textContent = name;
    mopen.href = url;
    mtoast.hidden = true;
    drawQR(url);
    modal.hidden = false;
  }
  function closeModal() { modal.hidden = true; }

  grid.addEventListener("click", e => {
    const btn = e.target.closest("[data-install]");
    if (!btn) return;
    if (isMobile) return; // let the link navigate to Waze
    e.preventDefault();
    openModal(btn.dataset.install, btn.dataset.name);
  });
  document.getElementById("mclose").addEventListener("click", closeModal);
  modal.addEventListener("click", e => { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
  mcopy.addEventListener("click", () => {
    const done = () => { mtoast.hidden = false; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(currentUrl).then(done, fallbackCopy);
    } else fallbackCopy();
    function fallbackCopy() {
      const ta = document.createElement("textarea");
      ta.value = currentUrl; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch (_) {}
      document.body.removeChild(ta); done();
    }
  });

  qEl.addEventListener("input", e => { state.q = e.target.value; render(); });
  langEl.addEventListener("change", e => { state.lang = e.target.value; render(); });
  catGroup.addEventListener("click", e => {
    const btn = e.target.closest("button");
    if (!btn) return;
    state.cat = btn.dataset.cat;
    catGroup.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b === btn)));
    render();
  });

  render();
</script>
</body>
</html>
"""


def generate_site(data_path: str = DATA_PATH, qr_js_path: str = QR_JS_PATH,
                  output_path: str = OUTPUT_PATH) -> int:
    with open(data_path, "r", encoding="utf-8") as f:
        waze_vps = json.load(f)
    with open(qr_js_path, "r", encoding="utf-8") as f:
        qr_js = f.read()

    records = build_records(waze_vps)
    data_json = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("__QRJS__", qr_js).replace("__DATA__", data_json)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {output_path} with {len(records)} voicepacks.")
    return len(records)


if __name__ == "__main__":
    generate_site()
