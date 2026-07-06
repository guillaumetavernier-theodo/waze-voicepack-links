"""Run the mp3_upload pipeline for the packs currently in input_packs/ and emit
the resulting Waze share links as JSON.

Invoked as a subprocess by serve.py so that a pipeline failure (including the
``sys.exit()`` inside file_upload.returnLoginHeader) can never take down the
bridge server. All human-readable pipeline logging goes to stdout as usual; the
machine-readable result is printed on a single line prefixed with
``PIPELINE_RESULT_JSON:`` for the caller to parse.

Usage:
    python helper_files/pipeline_runner.py
"""

import contextlib
import io
import json
import os
import re
import sys

MARKER = "PIPELINE_RESULT_JSON:"
_LINK_RE = re.compile(r"https://waze\.com/ul\?acvp=[0-9a-fA-F-]+")


def _emit(payload):
    print(MARKER + json.dumps(payload))


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # The pipeline uses ./mp3_upload/... relative paths (and os.getcwd()).
    os.chdir(root)
    sys.path.insert(0, os.path.join(root, "mp3_upload"))

    try:
        import file_ingestion
        import file_compression
        import file_upload
    except Exception as e:  # noqa: BLE001 — surface any dependency problem cleanly
        _emit({"ok": False, "error": f"Pipeline dependencies unavailable: {e}. "
               "Install the packages in requirements.txt (pydub, requests, "
               "blackboxprotobuf, ...)."})
        return

    input_dir = os.path.join(root, "mp3_upload", "input_packs")
    valid_file = os.path.join(root, "mp3_upload", "valid_waze_filenames.txt")

    try:
        packs = file_ingestion.ingest_mp3_packs(input_dir, valid_file)
    except Exception as e:  # noqa: BLE001
        _emit({"ok": False, "error": f"Ingestion failed: {e}"})
        return

    if not packs:
        _emit({"ok": False, "error": "No valid pack found — a pack needs at least "
               "one recognized Waze prompt mp3."})
        return

    try:
        file_compression.compress_mp3_packs(packs)
    except Exception as e:  # noqa: BLE001
        _emit({"ok": False, "error": f"Compression failed (is ffmpeg installed?): {e}"})
        return

    compressed_root = os.path.join(root, "mp3_upload", "compressed_packs")
    results = []
    try:
        folders = [f for f in os.listdir(compressed_root)
                   if os.path.isdir(os.path.join(compressed_root, f))]
    except FileNotFoundError:
        folders = []

    for folder in folders:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                file_upload.upload(folder)
        except SystemExit:
            # returnLoginHeader() calls sys.exit() on an auth failure.
            pass
        except Exception as e:  # noqa: BLE001
            results.append({"name": folder, "error": f"Upload error: {e}"})
            continue
        out = buf.getvalue()
        match = _LINK_RE.search(out)
        if match:
            results.append({"name": folder, "link": match.group(0)})
        else:
            results.append({"name": folder,
                            "error": "Upload did not return a link "
                                     "(authentication or network failure).",
                            "log": out[-600:]})

    # Clean up the transient archive file the uploader leaves in the cwd.
    try:
        os.remove(os.path.join(root, "ready.tar.gz"))
    except OSError:
        pass

    _emit({"ok": True, "results": results})


if __name__ == "__main__":
    main()
