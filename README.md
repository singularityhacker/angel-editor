# Angel Editor

A local-first command-line tool for filtering language, nudity and sexual content, and violence in video you lawfully own, for private viewing.

> **Status: early, v0 in progress.** Nothing here is released yet. There is no installable package, and the commands in this README are the planned interface, not working software. See the [roadmap](docs/ROADMAP.md) for what is being built and in what order.

## What it is

Angel Editor scans a video file on your own machine, finds the moments you might want to filter, and applies a profile you wrote. By default it produces a plain-text filter file that your player reads during playback. Your original file is not modified.

- **Local first.** Analysis runs on your machine. The core works offline.
- **Your thresholds.** A filter profile is a plain config file with per-category settings.
- **Inspectable.** Every action records what was detected, by which method, with what confidence, and which rule fired. You can read and edit the result before using it.
- **Optional cloud AI.** Later versions may let you send a small number of selected frames to a model provider using your own API key. This is opt-in per feature and off by default.

## Private use and legal framing

Angel Editor is a tool for creating personal viewing filters for videos you lawfully own.

- It does not circumvent DRM. Supply files you are entitled to use.
- It does not download, stream, or distribute media, and it never uploads your files.
- By default it writes a **sidecar filter file (EDL)** that your player applies during private playback. This is the case the US Family Movie Act of 2005 (17 U.S.C. §110(11)) was written for: making limited portions of a lawfully obtained copy imperceptible during private home viewing, with no fixed altered copy created.
- Optional features that **render an edited copy** or **generate bridge clips** go beyond what that Act addresses. They create a fixed copy, and generated bridges also add content. They are intended for private use only. Do not share their output. Using them is your responsibility.
- Optional cloud AI features send frames to a third party with your own API key. Check that provider's terms.
- Filter profiles are safe to share. Rendered films and bridge clips are not.

This project is not legal advice and is not affiliated with any studio or filtering service. Laws differ by country, and you are responsible for following yours. The research notes still list a legal review as an open item before render and generate features ship. See [docs/research/genfill-legal-positioning.md](docs/research/genfill-legal-positioning.md).

## How it works

1. **Analyze.** Probe the file, then find events. For language, use matching subtitles as a fast path where they exist, and transcribe locally with Whisper-family models to get word-level timestamps. Match words against a versioned profanity list with severity tiers. Each event gets a category, a severity, and a confidence score, and is stored in a canonical JSON timeline.
2. **Decide.** Apply your filter profile. An event becomes an action (mute, bleep, skip) when its severity reaches the profile's `min_severity` for that category. Manual overrides win, and skip wins over mute where intervals overlap.
3. **Output.** Either:
   - write a **sidecar** (default), leaving the original untouched, or
   - **render** a new copy with ffmpeg. In v0 this means re-encoding the audio and copying the video.
4. **Review.** The timeline and sidecar are plain text. Inspect them and hand-tune them before you play or render.

### Player compatibility

One `.edl` file does not work the same way across players. Kodi and MPlayer use related but different EDL formats, and mpv's EDL is a different thing entirely: it describes retained segments, not cuts and mutes. Angel Editor plans to export Kodi and MPlayer EDLs separately, and to handle mpv through retained-segment EDL for cuts plus a playback adapter for muting. Native Plex and Jellyfin clients should not be assumed to read arbitrary mute sidecars.

## Planned usage

**Not implemented yet.** This shows the intended interface and may change.

```bash
# Check ffmpeg, hardware, and model availability
angel doctor

# Analyze a file or a folder; writes a JSON timeline and caches intermediate results
angel analyze ./Season1/ --profile family.toml

# Write sidecar EDL files (default, non-destructive)
angel export ./Season1/ --profile family.toml --format kodi

# Or render an edited copy (audio re-encoded, video copied); private use only
angel render ./Season1/S01E01.mkv --profile family.toml
```

### Planned filter profile

```toml
[language]
min_severity = 2      # 1 mild, 2 strong, 3 explicit/severe
action = "mute"       # or "bleep"

[nudity]              # v1
min_severity = 1
action = "skip"

["violence.gore"]     # v1
min_severity = 3
action = "skip"
```

An action applies when an event's `severity >= min_severity`. Severity, detector confidence, and review status are kept separate. Severity tiers are editable definitions, not universal ratings.

## Roadmap summary

Full detail, including scope and done-when criteria, is in [docs/ROADMAP.md](docs/ROADMAP.md).

| Version | Focus |
|---|---|
| **v0** | Language filtering: subtitle fast path, local speech recognition with word timestamps, profanity tiers, JSON timeline, Kodi/MPlayer EDL, audio-only ffmpeg render, batch mode, `angel doctor`. |
| **v1** | Visual detection: shot detection, nudity detection, violence candidates, adaptive resampling, scene-range review. |
| **v2** | Optional AI severity grading with a local or hosted vision-language model. Unknown never counts as safe. |
| **v3** | Gap filling with a fallback chain. Highest legal risk, private use only. |

## How it compares

This table is based on the project's own research, which was not independently verified in every case. Items marked "unconfirmed" or "not verified" could not be checked. Pricing and operating status can change, so check the vendors directly.

| | **Angel Editor** | **VidAngel** | **ClearPlay** | **SkipIt** |
|---|---|---|---|---|
| Model | Open-source CLI, local | Commercial service; current status unconfirmed | Subscription (about $8/month, per a review site) | Startup; not verified |
| Content source | Your own files | Streaming catalog | Streaming via extension, discs | Streaming |
| Filter data | Generated locally by you | Curated tags | Curated by the vendor | Pre-scene alerts (crowd and AI claims unverified) |
| Works offline | Yes (core) | No | Partly | No |
| Output | EDL; optional render | Streamed edit | Playback skip | Playback skip and alerts |
| Customizable | Plain config | Per category | Per category | Per category |
| Data stays on your machine | By default | Account and viewing data on vendor servers | Same | Same |
| Legal background | Private use of files you own | Lost to the studios; paid a reported $9.9M settlement | Playback filtering, the model the Act was written for | Unclear |
| Gap filling | Planned (v3) | No | No | No |

Angel Editor is a work in progress and does not match these services today. It has no catalog, no pre-built filters, and no shipped features yet. The research also found no active open-source project that combines local speech and vision analysis with EDL output, but GitHub was not checked directly, so treat that as unconfirmed.

## Documentation

- [docs/VISION.md](docs/VISION.md): goals, boundaries, and principles
- [docs/ROADMAP.md](docs/ROADMAP.md): milestones and acceptance criteria
- [docs/research/detection-and-rendering.md](docs/research/detection-and-rendering.md): speech, visual detection, formats, and rendering
- [docs/research/genfill-legal-positioning.md](docs/research/genfill-legal-positioning.md): gap filling, legal framing, and positioning

## License

No license has been chosen yet, so no license grant applies to this code at this time.
