# Angel Editor

Angel Editor v1 is a local Python CLI for filtering language in videos you lawfully own for private viewing. It writes `<stem>.angel.mp4` beside the input, mutes or bleeps language across all audio channels, and optionally detects visual content and skips scenes. Video is stream-copied when there are no skips; cuts use libx264 (CRF 18). It never modifies the input.

Status: v1 visual detection and scene skipping implemented with mocked model tests and generated-media render tests. Detection quality on real films has not yet been benchmarked. Generative features are future work.

## Install

Requires Python 3.10+ and `ffmpeg`/`ffprobe` on PATH (on Debian/Ubuntu: `sudo apt-get install ffmpeg`). From this checkout:

```bash
pipx install .
# or
uv tool install .
# Optional local speech recognition:
pipx install '.[speech]'
# Optional visual detection (or use [all] for speech + visual):
pipx install '.[visual]'
```

The core works with SRT/VTT or embedded text subtitles without speech dependencies. The optional faster-whisper backend downloads the selected model on first use; cache it before working offline. Models and media stay local.

## Quickstart

```bash
angel doctor
angel clean movie.mp4
angel clean movie.mp4 --mode bleep --json --edl kodi
angel scan movie.mp4 --asr off
angel run movie.mp4 --nudity-threshold 0.7 --violence-threshold 0.8
angel run movie.mp4 --no-visual
angel clean ./Season1 --recursive -o ./cleaned
```

For batch `-o`, create the output directory first. Batch processing continues after errors, reports each file, and exits nonzero if any fail. Generated `.angel.mp4` files are excluded from directory scans.

## Usage

```text
angel run INPUT [INPUT ... | DIR] [-o OUT]
  [--mode mute|bleep] [--strictness mild|moderate|strict]
  [--subs auto|PATH|off] [--asr auto|off] [--model small] [--language en]
  [--pad-before 100] [--pad-after 150] [--bleep-level -18]
  [--profile PROFILE] [--edl kodi|mplayer] [--json] [--dry-run]
  [--no-cache] [--recursive] [--overwrite]
  [--no-visual] [--sample-fps 2] [--dense-fps 8] [--snap-window 0.75]
  [--nudity-threshold FLOAT] [--violence-threshold FLOAT]
  [--violence-model ViT-B-32] [--preset medium]
angel scan INPUT
angel doctor
```

`moderate` filters severity 2 and 3; `strict` includes severity 1; `mild` filters only severity 3. Padding is in milliseconds. Overlapping intervals and gaps under 50 ms are merged. Bleep level is in dBFS. JSON and EDL exports use the output stem (`movie.angel.json`, `movie.angel.edl`); EDL contains padded mute intervals and cuts (action 1 = mute, 0 = cut), in source time, while JSON preserves detection evidence and settings. Kodi and MPlayer export separately; other players are not supported. Scan writes `<stem>.angel.json` and prints JSON without rendering; dry run reports analysis without writing output or exports (transcripts can still be cached).

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

Limitations: subtitle wording and sync can differ from audio, and Whisper can omit or mis-time words. Analysis uses the first audio track; the same edit intervals apply to all output audio tracks, so multilingual tracks require care. CPU int8 is the current speech backend. AAC encoding changes audio quality; mute timing uses ffmpeg audio frames. MP4-compatible video and auxiliary streams are required: text subtitles convert to `mov_text`; unsupported streams, including bitmap subtitles, produce an explicit failure. No OCR, manual timeline import, or real-player EDL validation is included. Cuts retain the primary video and all audio tracks; subtitles, chapters, attachments, and additional video streams are omitted on the cut path. Without cuts, v0 stream preservation still applies.

## Visual analysis

`run` and `clean` are aliases. Visual stages run by default with `[visual]` installed;
core-only installs report that visual analysis is unavailable. `--no-visual` disables it.
NudeNet scores exposed classes only. The pluggable `VisualDetector` protocol also supports
an OpenCLIP zero-shot violence/blood/gore prompt classifier. `--violence-model` selects
the OpenCLIP architecture (default ViT-B-32, pretrained laion2b_s34b_b79k).
Model libraries may download weights on first use; prepare their caches for offline work.
`angel doctor` reports missing extras. Models are never bundled.

Frames stream directly from ffmpeg as BGR pixels, with both dimensions capped at 640
pixels, bounded buffering, and no temporary frame files. Presentation timestamps are
retained for base sampling and refinement. Base sampling is 2 fps. Scores at or above
the review threshold trigger a merged ±2-second window at 8 fps. Hits merge across gaps under one second, receive padding, snap to
PySceneDetect ContentDetector cuts within 0.75 seconds, and are dropped below minimum
duration. Skip takes priority over mute. Mutes are applied in source time before the
same A/V retained segments are concatenated, so edits after cuts remain synchronized.
Per-frame scores are cached by the v0 source fingerprint (size, mtime, first/last MiB),
sampling format, detector model ID, base/dense fps, and review threshold. Policy thresholds can be reapplied without inference.

Visual TOML rules use seconds for all durations:

```toml
[nudity]
enabled = true
threshold = 0.65
review_threshold = 0.325
min_duration = 0.25
pad_before = 0.25
pad_after = 0.25
action = "skip" # or "flag" to record without cutting

[violence]
enabled = true
threshold = 0.8
action = "flag"
```

Defaults for both categories: lenient (also `mild`) threshold 0.85, moderate 0.65,
strict 0.45; review threshold is half the preset threshold and never exceeds the
resolved action threshold. Other defaults match the example above. CLI thresholds
override TOML, which overrides the preset. `--subs off --asr off` explicitly disables
language analysis for a visual-only run. JSON schema 2 adds visual events with category,
score, labels, source model, action, and integer microsecond ranges.

These scores are uncalibrated candidates. A 0.2-second exposure can fall between base
samples and never trigger refinement. Swimwear, medical scenes, animation, red liquids,
sports, and weapons may cause errors; no real-film recall or safety guarantee is claimed.

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
