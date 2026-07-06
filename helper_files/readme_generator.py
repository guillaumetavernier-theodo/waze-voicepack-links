import json
import os

with open('helper_files/waze_vps.json', 'r', encoding='utf-8') as f:
    waze_vps_json = f.read()

SHARE_BASE_URI = "https://waze.com/ul?acvp="
FILES_BASE_URI = "https://voice-prompts-ipv6.waze.com/"
FILES_URI_SUFFIX = ".tar.gz"

def generate_official_voicepacks_markdown_table(waze_vps_json) -> str:
    waze_vps = json.loads(waze_vps_json)
    official_voicepacks = waze_vps.get("Official Voicepacks", [])

    # sort official voicepacks by name (case-insensitive) before rendering
    official_voicepacks = sorted(official_voicepacks, key=lambda vp: (vp.get("name") or "").lower())
    
    markdown_table = "| Name | Link | Language | mp3 files | Notes |\n"
    markdown_table += "|------|----------|----------|-----------|-------|\n"
    
    for vp in official_voicepacks:
        name = vp.get("name", "N/A")
        language = vp.get("language", "N/A")
        uuid = vp.get("uuid", "N/A")
        notes = vp.get("notes", "")
        blog = vp.get("blog", "")
        if blog:
            notes = f"[Blog Post]({blog}) " + notes
        share_link = f"{SHARE_BASE_URI}{uuid}"
        files_link = f"{FILES_BASE_URI}{uuid}{FILES_URI_SUFFIX}"
        markdown_table += f"| {name} | [Link]({share_link}) | {language} | [mp3 files]({files_link}) | {notes} |\n"
    
    return markdown_table

def generate_community_voicepacks_markdown_table(waze_vps_json) -> str:
    waze_vps = json.loads(waze_vps_json)
    community_voicepacks = waze_vps.get("Community Voicepacks", [])

    # sort community voicepacks by name (case-insensitive) before rendering
    community_voicepacks = sorted(community_voicepacks, key=lambda vp: (vp.get("name") or "").lower())
    
    markdown_table = "| Name | Link | Language | mp3 files | Notes |\n"
    markdown_table += "|------|----------|----------|-----------|-------|\n"
    
    for vp in community_voicepacks:
        name = vp.get("name", "N/A")
        language = vp.get("language", "N/A")
        uuid = vp.get("uuid", "N/A")
        share_link = f"{SHARE_BASE_URI}{uuid}"
        files_link = f"{FILES_BASE_URI}{uuid}{FILES_URI_SUFFIX}"
        # if the vp has the "author" field, include it in the notes
        author = vp.get("author", "")
        author_link = vp.get("author_link", "")
        author_2 = vp.get("author_2", "")
        author_2_link = vp.get("author_2_link", "")
        mp3_files_additional_note = vp.get("mp3_files_additional_note", "")
        json_notes = vp.get("notes", "")
        if author:
            if author_link:
                notes = f"By [{author}]({author_link})"
            else:
                notes = f"By {author}"
            if author_2_link:
                notes += f" and [{author_2}]({author_2_link})"
            elif author_2:
                notes += f" and {author_2}"
        else:
            notes = ""
        
        if json_notes:
            notes += f" {json_notes}"

        markdown_table += f"| {name} | [Link]({share_link}) | {language} | [mp3 files{mp3_files_additional_note}]({files_link}) | {notes} |\n"
    
    return markdown_table

intro_string = """# Waze Voicepack Links

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

- **Open it locally:** open [`docs/index.html`](docs/index.html) in your browser, or
  serve the repo with `python -m http.server` and visit `/docs/`.
- **Create packs from the app:** run `python serve.py` (a small stdlib bridge server)
  instead of a plain static server. Its **＋ Create pack from mp3s** button validates
  your mp3s and — with ffmpeg and the `requirements.txt` packages installed — runs the
  full ingestion → compression → Waze upload pipeline and adds the resulting link to
  your local list.
- The app is generated from [`helper_files/waze_vps.json`](helper_files/waze_vps.json)
  (the single source of truth) by
  [`helper_files/site_generator.py`](helper_files/site_generator.py). **Re-run that
  script after editing the JSON** to refresh the page (see below).

---

# Waze Voice Lists

The archive is split into two groups, both browsable in the web app:

- **Official** — current and former contracted celebrities and voice actors whose
  voices were once officially on the Waze app, saved and converted into user-made
  custom packs with shareable links of varying quality.
- **Community** — user-created voice packs made by the Waze community, recorded
  in-app or uploaded as `.mp3` files. Quality varies with the source audio.
"""

community_list_intro_string = """
# Waze Community Voice List

This list contains user-created voice packs made by the Waze community. These voices are often created using the in-app microphone recording feature or by uploading `.mp3` files to Waze's servers. The quality of these voice packs can vary greatly depending on the source of the audio files used to create them.
"""

outro_string = """
## Have mp3 files?
See these [instructions](https://github.com/pipeeeeees/waze-voicepack-links/tree/main/mp3_upload#how-to-upload-your-own-mp3-files-to-make-a-waze-voicepack-link) on how to upload using this repository.

The Android Emulator method is no longer recommended due to its complexity and manual effort required. 

The advantage of using files to create packs rather than using the in-app microphone is the preservation of audio quality. By default, Waze heavily compresses the in-app recordings making them sound muffled. While the file upload method may also involve some file compression on the server side, the audio quality is far superior to the in-app recording method. 

## Stance on A.I. Generated Voicepacks
Given the proliferation of A.I. voice generation tools in the hands of the public, there is an influx of A.I. generated Waze navigation voicepacks. These are often created without the explicit permission of the person or IP owner these voices belong to. This is a clear concern.

The purpose of this repository is to act as an archive of the internet's Waze voicepacks while providing tools to create permanent shareable Waze voicepack links. As the creator of this repository, I do not own the voice content stored on Waze's servers - only the files and text in this repository. To address the ethical concerns surrounding A.I. generated voicepacks, I have established the following guidelines:
- Any known A.I. voicepacks will be labeled as such in the name of the pack in the archive. If you find a voice in the archive to be A.I. generated but not correctly labeled, please open an issue or a pull request with the corrected title.
- If the voice actor or IP owner for an A.I. generated voicepack in the archive would like to have a pack removed, the request will be honored. Please open a new issue with the request and I or a contributor will get back to you.

"""

def generate_readme(waze_vps_json):
    # The full voicepack tables have been replaced by the web app
    # (docs/index.html), generated by site_generator.py. The table-building
    # helpers above are kept for reference / potential reuse but are no longer
    # embedded in the README.
    counts = json.loads(waze_vps_json)
    n_official = len(counts.get("Official Voicepacks", []))
    n_community = len(counts.get("Community Voicepacks", []))
    count_line = (f"\n> Currently archiving **{n_official} official** and "
                  f"**{n_community} community** voicepacks. "
                  f"Browse them in [`docs/index.html`](docs/index.html).\n")

    readme_content = f"{intro_string}\n{count_line}\n{outro_string}"

    # Write the repository's root README.md (the visible one).
    cwd = os.getcwd()
    readme_path = os.path.join(cwd, 'README.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)




if __name__ == "__main__":
    
    #official_table = generate_official_voicepacks_markdown_table(waze_vps_json)
    #community_table = generate_community_voicepacks_markdown_table(waze_vps_json)

    generate_readme(waze_vps_json)