# Waze Voicepack Links

A community-maintained archive of classic and custom Waze GPS voices — all in one place.

Bring back your favorite characters, celebrities, and custom voice packs that have disappeared from the official app over the years.

## 🚗 What Is This?

This repository collects publicly shareable Waze voicepack links so they don’t get lost in old Reddit threads, dead websites, or outdated blog posts.

**If you’ve ever thought:**

> “Where did my favorite Waze voice go?”

**This is for you.**

The goal is to keep these voices:
- Easy to find
- Easy to install
- Community-maintained

## 📲 How to Install a Voicepack

1. Install the **Waze app** on your phone.
2. Open the **voicepack browser** (see below) on the same device.
3. Tap **Install** on any voice.
4. Waze will open and download the voice.

## 🔎 Browse the voicepacks

The full, searchable list of voicepacks now lives in a lightweight, zero-dependency
web app instead of a giant table in this README. It supports search, language and
Official/Community filters, and shows a scannable QR code for each pack on desktop.

### Just browse (no setup)

Open [`docs/index.html`](docs/index.html) directly in your browser, or serve it with
`python -m http.server` and visit `/docs/`. No dependencies required.

### Launch with pack creation (uploads to Waze)

The **＋ Create pack from mp3s** button runs the full ingestion → compression → Waze
upload pipeline. That needs the local bridge server (`serve.py`), **ffmpeg**, and a few
Python packages. Set it up once:

**macOS / Linux**

```bash
# ffmpeg:  macOS -> brew install ffmpeg   |   Debian/Ubuntu -> sudo apt install ffmpeg
brew install ffmpeg

python3 -m venv .venv
.venv/bin/pip install pydub requests blackboxprotobuf protobuf
.venv/bin/pip install audioop-lts                 # only on Python 3.13+

.venv/bin/python helper_files/site_generator.py   # (re)build the app
.venv/bin/python serve.py                          # -> http://127.0.0.1:8912/
```

**Windows (PowerShell)**

```powershell
winget install Gyan.FFmpeg                 # or: choco install ffmpeg  (then reopen the shell)

python -m venv .venv
.venv\Scripts\pip install pydub requests blackboxprotobuf protobuf
.venv\Scripts\pip install audioop-lts       # only on Python 3.13+

.venv\Scripts\python helper_files\site_generator.py   # (re)build the app
.venv\Scripts\python serve.py                          # -> http://127.0.0.1:8912/
```

> **Notes**
> - `openai-whisper` in `requirements.txt` is **not** needed for the app or for uploads
>   (it pulls in PyTorch). The four packages above are all the pipeline requires.
> - `audioop-lts` is only required on **Python 3.13+**, where the stdlib `audioop`
>   module that `pydub` relies on was removed.
> - Launch `serve.py` with the **venv's** Python (as shown) — it runs the pipeline as a
>   subprocess using that same interpreter, so the packages must be visible to it.

The app is generated from [`helper_files/waze_vps.json`](helper_files/waze_vps.json)
(the single source of truth) by
[`helper_files/site_generator.py`](helper_files/site_generator.py). **Re-run that
script after editing the JSON** to refresh the page.

---

# Waze Voice Lists

The archive is split into two groups, both browsable in the web app:

- **Official** — current and former contracted celebrities and voice actors whose
  voices were once officially on the Waze app, saved and converted into user-made
  custom packs with shareable links of varying quality.
- **Community** — user-created voice packs made by the Waze community, recorded
  in-app or uploaded as `.mp3` files. Quality varies with the source audio.


> Currently archiving **86 official** and **96 community** voicepacks. Browse them in [`docs/index.html`](docs/index.html).


## Have mp3 files?
See these [instructions](https://github.com/pipeeeeees/waze-voicepack-links/tree/main/mp3_upload#how-to-upload-your-own-mp3-files-to-make-a-waze-voicepack-link) on how to upload using this repository.

The Android Emulator method is no longer recommended due to its complexity and manual effort required. 

The advantage of using files to create packs rather than using the in-app microphone is the preservation of audio quality. By default, Waze heavily compresses the in-app recordings making them sound muffled. While the file upload method may also involve some file compression on the server side, the audio quality is far superior to the in-app recording method. 

## Stance on A.I. Generated Voicepacks
Given the proliferation of A.I. voice generation tools in the hands of the public, there is an influx of A.I. generated Waze navigation voicepacks. These are often created without the explicit permission of the person or IP owner these voices belong to. This is a clear concern.

The purpose of this repository is to act as an archive of the internet's Waze voicepacks while providing tools to create permanent shareable Waze voicepack links. As the creator of this repository, I do not own the voice content stored on Waze's servers - only the files and text in this repository. To address the ethical concerns surrounding A.I. generated voicepacks, I have established the following guidelines:
- Any known A.I. voicepacks will be labeled as such in the name of the pack in the archive. If you find a voice in the archive to be A.I. generated but not correctly labeled, please open an issue or a pull request with the corrected title.
- If the voice actor or IP owner for an A.I. generated voicepack in the archive would like to have a pack removed, the request will be honored. Please open a new issue with the request and I or a contributor will get back to you.

