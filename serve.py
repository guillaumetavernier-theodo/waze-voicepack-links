"""Local bridge server for the Waze Voicepack web app.

Serves the static app (docs/) AND exposes a tiny API the in-app "Create pack
from mp3s" importer calls to actually run the pipeline:

    GET  /                 -> docs/index.html (and other static assets)
    GET  /api/health       -> {"ok": true, "ffmpeg": <bool>}
    POST /api/create-pack  -> body {"name": str, "files": [{"filename","b64"}]}
                              runs ingestion -> compression -> Waze upload and
                              returns {"ok": true, "results": [{"name","link"}]}

The pipeline runs in a subprocess (helper_files/pipeline_runner.py) so a
failure inside it can never crash this server. Stdlib only — no extra deps
beyond what the pipeline itself needs.

Run it from the repo root:

    python serve.py            # http://127.0.0.1:8912
    python serve.py 9000       # custom port

NOTE: uploading actually publishes a voicepack to Waze's servers and requires
ffmpeg plus the packages in requirements.txt. Bind is 127.0.0.1 (local only).
"""

import json
import os
import re
import shutil
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(ROOT, "docs")
INPUT_PACKS = os.path.join(ROOT, "mp3_upload", "input_packs")
RUNNER = os.path.join(ROOT, "helper_files", "pipeline_runner.py")
MARKER = "PIPELINE_RESULT_JSON:"

MAX_BODY = 25 * 1024 * 1024   # 25 MB cap on request bodies
PIPELINE_TIMEOUT = 600        # seconds

_NAME_RE = re.compile(r"[^A-Za-z0-9 ._-]")


def sanitize_pack_name(name):
    name = _NAME_RE.sub("_", (name or "").strip())
    name = name.strip(". ")
    return name or "My Pack"


def safe_mp3_name(filename):
    """Return a safe basename, or None if it isn't a plain .mp3 file."""
    base = os.path.basename((filename or "").replace("\\", "/"))
    if not base or base in (".", "..") or "/" in base:
        return None
    if not base.lower().endswith(".mp3"):
        return None
    return base


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DOCS_DIR, **kwargs)

    def log_message(self, fmt, *args):  # keep the console quiet-ish
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---- helpers ----
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    # ---- routes ----
    def do_GET(self):
        if self.path.split("?")[0] == "/api/health":
            self._send_json(200, {"ok": True, "ffmpeg": shutil.which("ffmpeg") is not None})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/create-pack":
            self._send_json(404, {"ok": False, "error": "Unknown endpoint."})
            return

        if shutil.which("ffmpeg") is None:
            self._send_json(400, {"ok": False, "error":
                "ffmpeg is required for compression but was not found on PATH. "
                "Install ffmpeg and restart the server."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._send_json(400, {"ok": False, "error": "Missing or oversized request body."})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:  # noqa: BLE001
            self._send_json(400, {"ok": False, "error": "Invalid JSON body."})
            return

        name = sanitize_pack_name(payload.get("name"))
        files = payload.get("files") or []
        if not isinstance(files, list) or not files:
            self._send_json(400, {"ok": False, "error": "No files provided."})
            return

        try:
            written = self._stage_pack(name, files)
        except Exception as e:  # noqa: BLE001
            self._send_json(400, {"ok": False, "error": f"Could not stage files: {e}"})
            return
        if written == 0:
            self._send_json(400, {"ok": False, "error":
                "None of the provided files were valid .mp3 files."})
            return

        result = self._run_pipeline()
        status = 200 if result.get("ok") else 502
        self._send_json(status, result)

    # ---- pipeline plumbing ----
    def _stage_pack(self, name, files):
        import base64
        # Work on a clean input_packs so only this pack is processed. Preserve
        # .gitkeep; remove any leftover pack directories from earlier runs.
        os.makedirs(INPUT_PACKS, exist_ok=True)
        for entry in os.listdir(INPUT_PACKS):
            p = os.path.join(INPUT_PACKS, entry)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
        pack_dir = os.path.join(INPUT_PACKS, name)
        os.makedirs(pack_dir, exist_ok=True)

        written = 0
        for item in files:
            base = safe_mp3_name(item.get("filename"))
            b64 = item.get("b64")
            if not base or not isinstance(b64, str):
                continue
            data = base64.b64decode(b64, validate=False)
            with open(os.path.join(pack_dir, base), "wb") as f:
                f.write(data)
            written += 1
        return written

    def _run_pipeline(self):
        try:
            proc = subprocess.run(
                [sys.executable, RUNNER],
                cwd=ROOT, capture_output=True, text=True, timeout=PIPELINE_TIMEOUT)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Pipeline timed out."}

        for line in proc.stdout.splitlines():
            if line.startswith(MARKER):
                try:
                    return json.loads(line[len(MARKER):])
                except Exception:  # noqa: BLE001
                    break
        tail = (proc.stderr or proc.stdout or "").strip()[-600:]
        return {"ok": False, "error": "Pipeline produced no result.",
                "log": tail}


def main():
    port = 8912
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    if not os.path.isdir(DOCS_DIR):
        sys.exit(f"docs/ not found at {DOCS_DIR} — run helper_files/site_generator.py first.")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Waze Voicepack app + pipeline bridge running at http://127.0.0.1:{port}/")
    print("  GET  /              -> the web app")
    print("  POST /api/create-pack -> runs ingestion → compression → Waze upload")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
