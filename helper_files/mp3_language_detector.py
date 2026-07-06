"""Language "detection" for voice packs — light build.

The original implementation used ``openai-whisper`` (which pulls in PyTorch)
to transcribe a prompt and infer the spoken language. That dependency has been
removed to keep this build lightweight. Language is now treated as a **manual
field**: these helpers keep the same public API but return ``"unknown"`` so
callers can fall back to a value entered by a human.

Public API (unchanged):
- detect_language_from_mp3(mp3_path) -> str
- analyze_pack(pack_path, verbose=False) -> dict
- deduce_primary_language(pack_path, verbose=False) -> str
"""

import os

import path_finder

# Sentinel returned when a language cannot be auto-detected. Fill this in
# manually (e.g. in waze_vps.json / the voice index) when adding a pack.
UNKNOWN_LANGUAGE = "unknown"


def detect_language_from_mp3(mp3_path: str) -> str:
    """Return the language of a single MP3.

    Whisper-based auto-detection was removed in the light build, so this always
    returns ``"unknown"``. Set the language manually when cataloguing a pack.
    """
    return UNKNOWN_LANGUAGE


def analyze_pack(pack_path: str, verbose: bool = False) -> dict:
    tally = {}
    # go over all the items in waze_filename_paths.json and tally languages
    if verbose:
        print(f"Analyzing voice pack at: {pack_path}...")
    for filename, waze_path in path_finder.filenames_and_paths.items():

        full_path = os.path.join(pack_path, waze_path)
        if os.path.exists(full_path):
            language = detect_language_from_mp3(full_path)
            if verbose:
                print(f"File: {waze_path} - Detected Language: {language}")
            # add to tally
            if language in tally:
                tally[language] += 1
            else:
                tally[language] = 1
        else:
            print(f"File: {waze_path} does not exist in the provided pack path.")

    return tally


def deduce_primary_language(pack_path: str, verbose: bool = False) -> str:
    tally = analyze_pack(pack_path, verbose)
    if not tally:
        return UNKNOWN_LANGUAGE
    # find the language with the highest count
    primary_language = max(tally, key=tally.get)
    return primary_language


if __name__ == "__main__":
    cwd = os.path.dirname(os.path.abspath(__file__))
    sample_pack_path = os.path.join(cwd, "test_packs", "Voice 2")

    print(deduce_primary_language(sample_pack_path))
