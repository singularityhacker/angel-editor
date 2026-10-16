# Angel Editor

Angel Editor v0 is a local Python CLI for filtering language in videos you lawfully own for private viewing. It writes `<stem>.angel.mp4` beside the input, copies the video without re-encoding, and mutes or bleeps detected language across every channel of every retained audio stream. It never modifies the input.

Status: v0 implemented with generated-media regression tests. Detection quality on real films has not yet been benchmarked. Visual filtering and generative features are future work.

## Install

Requires Python 3.10+ and `ffmpeg`/`ffprobe` on PATH (on Debian/Ubuntu: `sudo apt-get install ffmpeg`). From this checkout:

```bash
pipx install .
# or
uv tool install .
# Optional local speech recognition:
pipx install '.[speech]'
```

The core works with SRT/VTT or embedded text subtitles without speech dependencies. The optional faster-whisper backend downloads the selected model on first use; cache it before working offline. Models and media stay local.

## Quickstart

```bash
angel doctor
angel clean movie.mp4
angel clean movie.mp4 --mode bleep --json --edl kodi
angel scan movie.mp4 --asr off
angel clean ./Season1 --recursive -o ./cleaned
```

For batch `-o`, create the output directory first. Batch processing continues after errors, reports each file, and exits nonzero if any fail. Generated `.angel.mp4` files are excluded from directory scans.

## Usage

```text
angel clean INPUT [INPUT ... | DIR] [-o OUT]
  [--mode mute|bleep] [--strictness mild|moderate|strict]
  [--subs auto|PATH|off] [--asr auto|off] [--model small] [--language en]
  [--pad-before 100] [--pad-after 150] [--bleep-level -18]
  [--profile PROFILE] [--edl kodi|mplayer] [--json] [--dry-run]
  [--no-cache] [--recursive] [--overwrite]
angel scan INPUT
angel doctor
```

`moderate` filters severity 2 and 3; `strict` includes severity 1; `mild` filters only severity 3. Padding is in milliseconds. Overlapping intervals and gaps under 50 ms are merged. Bleep level is in dBFS. JSON and EDL exports use the output stem (`movie.angel.json`, `movie.angel.edl`); EDL contains padded mute intervals, while JSON preserves detection evidence and settings. Kodi and MPlayer export separately; other players are not supported. Scan prints JSON without rendering; dry run reports analysis without writing output or exports (transcripts can still be cached).

Subtitle auto mode checks matching `.srt`, `.vtt`, and `.en.srt`, then embedded text subtitles. With speech installed and enabled, matching cues are transcribed in one-second context windows for word timing. Otherwise the whole cue is muted and explicitly marked `accuracy: "cue"`. No subtitles requires the speech extra and enabled ASR. An unavailable analysis path fails rather than claiming the file is clean. No detections still writes a stream copy and reports “no changes”. Existing outputs require `--overwrite`.

Profiles are TOML, with category thresholds, allowlisted tokens/phrases, and additional lexicon entries:

```toml
allowlist = ["hell"]
extra_words = [{term = "custom phrase", variants = [], category = "profanity", severity = 2}]

[profanity]
min_severity = 2

[blasphemy]
min_severity = 1
```

Categories are `profanity`, `sexual`, `slur`, `blasphemy`, and `bodily`. The modest, versioned English lexicon uses whole tokens and explicit variants; it is not a comprehensive content rating system. Cache location defaults to `~/.cache/angel-editor`; override with `ANGEL_CACHE_DIR`. Transcripts are keyed by source size, mtime, first/last MiB, model, language, and transcription window. Profiles and padding are reapplied to cached transcripts.

Limitations: subtitle wording and sync can differ from audio, and Whisper can omit or mis-time words. Analysis uses the first audio track; the same edit intervals apply to all output audio tracks, so multilingual tracks require care. CPU int8 is the current speech backend. AAC encoding changes audio quality; mute timing uses ffmpeg audio frames. MP4-compatible video and auxiliary streams are required: text subtitles convert to `mov_text`; unsupported streams, including bitmap subtitles, produce an explicit failure. No automatic codec conversion, OCR, visual filtering, manual timeline import, or real-player EDL validation is included.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
scripts/ci-local.sh
```

Tests create tiny stereo and 5.1 media in temporary directories, run without network or real Whisper, and check packet-preserving video copy and audio signal behavior. CI installs ffmpeg and tests Python 3.10 and 3.12. Follow-ups include listening benchmarks on annotated dialogue/music/crosstalk, synchronization validation, selectable audio tracks, and real Kodi/MPlayer checks. See [VISION](docs/VISION.md), [roadmap](docs/ROADMAP.md), and [research](docs/research/detection-and-rendering.md); the v0 build spec narrows the broader roadmap.

## Private use

Supply files you lawfully own and are entitled to edit, for personal use only. Angel Editor never circumvents DRM, downloads, uploads, or distributes media. Keep rendered copies private. Saved edited copies and added bleep audio fall outside the playback-filter scenario described by the US Family Movie Act; laws vary by jurisdiction. This project is not legal advice. See the [legal research](docs/research/genfill-legal-positioning.md).

No license has been chosen; no license grant applies at this time.
