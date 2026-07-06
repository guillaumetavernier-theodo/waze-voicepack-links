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
VALID_FILENAMES_PATH = os.path.join(_repo_root, "mp3_upload", "valid_waze_filenames.txt")
OUTPUT_PATH = os.path.join(_repo_root, "docs", "index.html")

# Waze's per-pack size limit, mirrored from mp3_upload/file_compression.py
# (TARGET_FOLDER_SIZE = 0.795 MB, measured as bytes / 1024 / 1024).
SIZE_LIMIT_MB = 0.795


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
  .chip.cat-Imported { background: rgba(26,143,76,.18); color: #1a8f4c; }
  @media (prefers-color-scheme: dark) {
    .chip.cat-Official { color: #9fe4ff; }
    .chip.cat-Imported { color: #5fd693; }
  }
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
  /* Header row + create button */
  .header-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .create-btn { font: inherit; font-weight: 600; cursor: pointer; border: 1px solid var(--border);
    background: var(--accent); color: var(--accent-ink); border-radius: 10px; padding: 9px 14px; }
  /* Import panel (create-from-mp3s) */
  .sheet { position: fixed; inset: 0; background: var(--overlay); z-index: 60; display: flex;
    align-items: flex-start; justify-content: center; padding: 24px 16px; overflow-y: auto; }
  .sheet[hidden] { display: none; }
  .sheet-box { background: var(--card); border-radius: 16px; padding: 22px; max-width: 620px; width: 100%;
    position: relative; box-shadow: 0 20px 60px rgba(0,0,0,.35); }
  .sheet-box h2 { margin: 0 30px 6px 0; font-size: 20px; }
  .sheet-box .lead { color: var(--muted); margin: 0 0 16px; font-size: 14px; }
  .field { display: block; margin: 12px 0; }
  .field label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
  .field input[type=text] { width: 100%; font: inherit; color: var(--text); background: var(--bg);
    border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; }
  .pickers { display: flex; gap: 8px; flex-wrap: wrap; }
  .picker { position: relative; overflow: hidden; display: inline-flex; }
  .picker input[type=file] { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
  .picker span { border: 1px solid var(--border); background: var(--bg); border-radius: 10px;
    padding: 9px 14px; font-size: 14px; }
  .report { margin-top: 16px; }
  .report .stat { font-size: 14px; margin: 8px 0; }
  .report .ok { color: #1a8f4c; } .report .warn { color: #b8860b; } .report .bad { color: #c0392b; }
  @media (prefers-color-scheme: dark) { .report .ok { color: #5fd693; } .report .warn { color: #e2b23c; } .report .bad { color: #ff7a6b; } }
  .filelist { list-style: none; padding: 0; margin: 6px 0; max-height: 220px; overflow-y: auto;
    border: 1px solid var(--border); border-radius: 10px; }
  .filelist li { display: flex; align-items: center; gap: 8px; padding: 6px 10px; font-size: 13px;
    border-bottom: 1px solid var(--border); }
  .filelist li:last-child { border-bottom: 0; }
  .filelist .fn { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .filelist .sz { color: var(--muted); white-space: nowrap; }
  .filelist audio { height: 30px; }
  .missing-tags { display: flex; flex-wrap: wrap; gap: 5px; margin: 6px 0; }
  .missing-tags .chip { background: var(--chip); }
  .publish { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 14px; }
  .publish pre { background: var(--bg); border: 1px solid var(--border); border-radius: 10px;
    padding: 12px; overflow-x: auto; font-size: 13px; }
  .publish code { white-space: pre; }
</style>
</head>
<body>
<header>
  <div class="header-row">
    <h1>🚗 Waze Voicepack Links</h1>
    <button id="createBtn" class="create-btn">＋ Create pack from mp3s</button>
  </div>
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

<div class="sheet" id="sheet" hidden role="dialog" aria-modal="true" aria-labelledby="sheetTitle">
  <div class="sheet-box">
    <button class="modal-close" id="sheetClose" aria-label="Close">&times;</button>
    <h2 id="sheetTitle">Create a voicepack from mp3 files</h2>
    <p class="lead">Pick the mp3 files (or a folder) for your pack. This checks them against
      the filenames Waze recognizes and the pack size limit, right here in your browser — nothing
      is uploaded. To mint a shareable Waze link, finish with the Python pipeline (steps shown below).</p>

    <label class="field">
      <span style="display:block;font-size:13px;color:var(--muted);margin-bottom:4px">Pack name</span>
      <input type="text" id="packName" placeholder="e.g. My Custom Voice" autocomplete="off">
    </label>
    <label class="field">
      <span style="display:block;font-size:13px;color:var(--muted);margin-bottom:4px">Language (optional)</span>
      <input type="text" id="packLang" placeholder="e.g. English" autocomplete="off">
    </label>

    <div class="pickers">
      <label class="picker"><span>Choose mp3 files…</span>
        <input type="file" id="fileInput" multiple accept=".mp3,audio/mpeg"></label>
      <label class="picker"><span>Choose a folder…</span>
        <input type="file" id="dirInput" webkitdirectory></label>
    </div>

    <div class="report" id="report" hidden></div>
    <div class="publish" id="publish" hidden></div>
  </div>
</div>

<script>__QRJS__</script>
<script id="data" type="application/json">__DATA__</script>
<script>
  const BASE_DATA = JSON.parse(document.getElementById("data").textContent);
  const IMPORTED_KEY = "wvp_imported";
  function loadImported() {
    try { return JSON.parse(localStorage.getItem(IMPORTED_KEY) || "[]"); }
    catch (e) { return []; }
  }
  let DATA = BASE_DATA.concat(loadImported());
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
    document.getElementById("total").textContent = DATA.length;
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

  // --- Create a pack from mp3 files (client-side validation + handoff) ---
  (function importFeature() {
    const VALID_FILENAMES = __VALIDNAMES__;
    const SIZE_LIMIT_MB = __SIZELIMIT__;
    // Match filenames exactly (case-sensitive), same as the Python pipeline.
    const VALID = new Set(VALID_FILENAMES);
    const LOWER = new Map(VALID_FILENAMES.map(n => [n.toLowerCase(), n]));
    const sheet = document.getElementById("sheet");
    const report = document.getElementById("report");
    const publish = document.getElementById("publish");
    const packName = document.getElementById("packName");
    let objectUrls = [];
    let lastValid = [];
    let bridge = { checked: false, available: false, ffmpeg: false };

    async function healthCheck() {
      try {
        const r = await fetch("api/health", { cache: "no-store" });
        const j = await r.json();
        bridge = { checked: true, available: true, ffmpeg: !!j.ffmpeg };
      } catch (e) {
        bridge = { checked: true, available: false, ffmpeg: false };
      }
      if (!publish.hidden) renderPublish(lastValid.length > 0);
    }

    const openSheet = () => { sheet.hidden = false; healthCheck(); };
    const closeSheet = () => { sheet.hidden = true; };
    document.getElementById("createBtn").addEventListener("click", openSheet);
    document.getElementById("sheetClose").addEventListener("click", closeSheet);
    sheet.addEventListener("click", e => { if (e.target === sheet) closeSheet(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape" && !sheet.hidden) closeSheet(); });

    function escHtml(s) {
      return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }
    function fmtSize(b) {
      if (b >= 1048576) return (b / 1048576).toFixed(2) + " MB";
      if (b >= 1024) return (b / 1024).toFixed(1) + " KB";
      return b + " B";
    }
    function sanitize(name) { return (name || "").trim().replace(/[\\/:*?"<>|]/g, "_") || "My Pack"; }

    function handleFiles(fileList) {
      objectUrls.forEach(u => URL.revokeObjectURL(u)); objectUrls = [];
      const files = Array.from(fileList);
      if (!packName.value && files.length && files[0].webkitRelativePath) {
        const top = files[0].webkitRelativePath.split("/")[0];
        if (top) packName.value = top;
      }
      const valid = [], ignored = []; const present = new Set();
      for (const f of files) {
        const base = f.name;
        if (VALID.has(base)) {
          valid.push({ name: base, size: f.size, file: f }); present.add(base);
        } else {
          const canon = base.toLowerCase().endsWith(".mp3") ? LOWER.get(base.toLowerCase()) : null;
          ignored.push({ name: base, caseHint: (canon && canon !== base) ? canon : null });
        }
      }
      const missing = VALID_FILENAMES.filter(n => !present.has(n));
      const totalBytes = valid.reduce((a, f) => a + f.size, 0);
      lastValid = valid;
      renderReport({ valid, ignored, missing, totalBytes, totalMB: totalBytes / 1048576 });
      renderPublish(valid.length > 0);
    }

    function renderReport(r) {
      const packValid = r.valid.length > 0;
      const over = r.totalMB > SIZE_LIMIT_MB;
      let html = "";
      html += `<p class="stat ${packValid ? "ok" : "bad"}">${packValid ? "✓" : "✗"} ` +
        `${r.valid.length} recognized Waze prompt file${r.valid.length === 1 ? "" : "s"}` +
        (packValid ? "" : " — need at least one to make a valid pack") + `</p>`;
      if (r.valid.length) html += `<ul class="filelist" id="validList"></ul>`;
      html += `<p class="stat ${over ? "warn" : "ok"}">Pack size: ${fmtSize(r.totalBytes)} ` +
        `(limit ${SIZE_LIMIT_MB} MB) — ${over ? "over the limit; the pipeline will compress it down" : "within the limit"}</p>`;
      if (r.missing.length) {
        html += `<p class="stat warn">⚠ ${r.missing.length} prompt${r.missing.length === 1 ? "" : "s"} missing (will be silent/omitted):</p>`;
        html += `<div class="missing-tags">` + r.missing.map(n => `<span class="chip">${escHtml(n)}</span>`).join("") + `</div>`;
      }
      if (r.ignored.length) {
        html += `<p class="stat">ℹ ${r.ignored.length} file${r.ignored.length === 1 ? "" : "s"} ignored (not recognized Waze prompts): ` +
          r.ignored.slice(0, 12).map(i => escHtml(i.name)).join(", ") + (r.ignored.length > 12 ? "…" : "") + `</p>`;
        const hints = r.ignored.filter(i => i.caseHint);
        if (hints.length) {
          html += `<p class="stat warn">↳ ${hints.length} look like a prompt but have the wrong case — Waze needs an exact match, so rename:</p>`;
          html += `<ul class="filelist">` + hints.map(i =>
            `<li><span class="fn">${escHtml(i.name)}</span><span class="sz">→ ${escHtml(i.caseHint)}</span></li>`).join("") + `</ul>`;
        }
      }
      report.innerHTML = html; report.hidden = false;
      if (r.valid.length) {
        const ul = document.getElementById("validList");
        r.valid.sort((a, b) => a.name.localeCompare(b.name));
        for (const v of r.valid) {
          const url = URL.createObjectURL(v.file); objectUrls.push(url);
          const li = document.createElement("li");
          li.innerHTML = `<span class="fn">${escHtml(v.name)}</span><span class="sz">${fmtSize(v.size)}</span>`;
          const audio = document.createElement("audio");
          audio.controls = true; audio.preload = "none"; audio.src = url;
          li.appendChild(audio); ul.appendChild(li);
        }
      }
    }

    function manualInstructionsHtml(name) {
      return `<h3 style="margin:0 0 8px;font-size:15px">Publish it (get a shareable Waze link)</h3>` +
        `<p class="stat" style="color:var(--muted)">Run the repo's bridge server (<code>python serve.py</code>) to create the link from here, or do it manually:</p>` +
        `<pre><code># 1. Put these mp3s in a folder named after the pack:\n` +
        `mp3_upload/input_packs/${escHtml(name)}/\n\n` +
        `# 2. Install ffmpeg + the Python deps (requirements.txt), then run:\n` +
        `python mp3_upload/main.py\n\n` +
        `# 3. On success it prints your https://waze.com/ul?acvp=... link.</code></pre>`;
    }

    function renderPublish(show) {
      if (!show) { publish.hidden = true; publish.innerHTML = ""; return; }
      const name = sanitize(packName.value);
      publish.hidden = false;
      if (bridge.available && bridge.ffmpeg) {
        publish.innerHTML =
          `<h3 style="margin:0 0 8px;font-size:15px">Create the link</h3>` +
          `<p class="stat" style="color:var(--muted)">Runs ingestion → compression → Waze upload through the local bridge, then adds the link to the list below. This can take a bit.</p>` +
          `<button id="uploadBtn" class="create-btn">⬆ Upload &amp; create link</button>` +
          `<div class="stat" id="uploadStatus" style="margin-top:10px"></div>`;
        document.getElementById("uploadBtn").addEventListener("click", doUpload);
      } else {
        const banner = (bridge.available && !bridge.ffmpeg)
          ? `<p class="stat bad">Bridge server is running but ffmpeg wasn't found — install ffmpeg and restart <code>serve.py</code> to create links from here.</p>`
          : "";
        publish.innerHTML = banner + manualInstructionsHtml(name);
      }
    }

    function fileToB64(file) {
      return new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => { const s = String(r.result); resolve(s.slice(s.indexOf(",") + 1)); };
        r.onerror = reject;
        r.readAsDataURL(file);
      });
    }

    function addImported(name, lang, link) {
      const uuid = (link.match(/acvp=([0-9a-fA-F-]+)/) || [])[1] || "";
      const rec = { name: name, language: lang || "Unknown", category: "Imported",
        install: link, mp3: "https://voice-prompts-ipv6.waze.com/" + uuid + ".tar.gz",
        notes: "Created locally via the pipeline", blog: "", author: "", author_link: "", imported: true };
      const arr = loadImported(); arr.push(rec);
      localStorage.setItem(IMPORTED_KEY, JSON.stringify(arr));
      DATA.push(rec); render();
    }

    async function doUpload() {
      const btn = document.getElementById("uploadBtn");
      const status = document.getElementById("uploadStatus");
      const name = sanitize(packName.value);
      const lang = (document.getElementById("packLang").value || "").trim();
      if (!lastValid.length) { status.innerHTML = `<span class="bad">Add at least one recognized prompt first.</span>`; return; }
      btn.disabled = true;
      status.textContent = "Uploading & running the pipeline… (compression + upload can take a bit)";
      try {
        const files = await Promise.all(lastValid.map(async v => ({ filename: v.name, b64: await fileToB64(v.file) })));
        const resp = await fetch("api/create-pack", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name, files: files }) });
        const data = await resp.json();
        if (!data.ok) { status.innerHTML = `<span class="bad">❌ ${escHtml(data.error || "Failed")}</span>`; btn.disabled = false; return; }
        const made = (data.results || []).filter(r => r.link);
        if (!made.length) {
          const err = (data.results && data.results[0] && data.results[0].error) || "No link was produced.";
          status.innerHTML = `<span class="bad">❌ ${escHtml(err)}</span>`; btn.disabled = false; return;
        }
        made.forEach(r => addImported(name, lang, r.link));
        status.innerHTML = `<span class="ok">✅ Created and added to the list below:</span><br>` +
          made.map(r => `<a href="${escHtml(r.link)}" target="_blank" rel="noopener">${escHtml(r.link)}</a>`).join("<br>");
      } catch (e) {
        status.innerHTML = `<span class="bad">❌ ${escHtml(String(e))} — is the bridge server running (python serve.py)?</span>`;
        btn.disabled = false;
      }
    }

    document.getElementById("fileInput").addEventListener("change", e => handleFiles(e.target.files));
    document.getElementById("dirInput").addEventListener("change", e => handleFiles(e.target.files));
    packName.addEventListener("input", () => { if (!publish.hidden) renderPublish(true); });
  })();

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


def load_valid_filenames(path: str = VALID_FILENAMES_PATH) -> list:
    """Read the canonical Waze prompt filenames (one per line)."""
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def generate_site(data_path: str = DATA_PATH, qr_js_path: str = QR_JS_PATH,
                  output_path: str = OUTPUT_PATH) -> int:
    with open(data_path, "r", encoding="utf-8") as f:
        waze_vps = json.load(f)
    with open(qr_js_path, "r", encoding="utf-8") as f:
        qr_js = f.read()
    valid_filenames = load_valid_filenames()

    records = build_records(waze_vps)
    data_json = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    html = (HTML_TEMPLATE
            .replace("__QRJS__", qr_js)
            .replace("__DATA__", data_json)
            .replace("__VALIDNAMES__", json.dumps(valid_filenames, ensure_ascii=False))
            .replace("__SIZELIMIT__", repr(SIZE_LIMIT_MB)))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {output_path} with {len(records)} voicepacks.")
    return len(records)


if __name__ == "__main__":
    generate_site()
