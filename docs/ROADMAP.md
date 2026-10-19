# Angel Editor: Roadmap

This roadmap follows [VISION.md](VISION.md) and the research in [docs/research/](research/). v0 and the narrowed v1 implementation are shipped; broader research goals below remain open. Metrics named in "done when" are measured on a human-annotated test set (dialogue, music, crosstalk, animation, brief exposure, graphic and non-graphic action). Numeric targets are left as "set after baseline" where the research gives no figure, because it says benchmarks should decide thresholds.

Shared rules for all milestones:

- Intervals are half-open `[start, end)`, stored as integer microseconds in original presentation timestamps. Never compute time as `frame_number / nominal_fps`.
- The canonical JSON timeline is the source of truth. EDL files are exports and cannot hold categories, confidence, or provenance.
- An edited copy (MP4 in, clean MP4 out) is the default output. Sidecar EDL/JSON exports are optional flags.
- Cloud features are opt-in, use the user's own key, and send minimal data.
- Unknown or failed analysis is never treated as safe.

## v0: language filtering that works

**Goal.** Reliably mute or bleep profanity in files the user owns, producing a clean edited MP4 by default (audio re-encoded, video stream-copied), with optional EDL/JSON sidecars.

**Scope**
- Python 3.11 CLI (`angel`), `pyproject.toml`, `src/angel_editor/` layout, optional extras (for example `[speech]`, `[align]`).
- `ffprobe`-based probe: tracks, timestamps, duration, and an edition fingerprint. The user selects the audio track and language explicitly.
- Subtitle fast path: embedded text subtitles and `.srt`, `.vtt`, `.ass` sidecars. Validate language and sync, match profanity, and force-align matching cues plus nearby audio. If alignment fails, offer whole-cue muting with a visible accuracy warning.
- Local speech recognition with word timestamps: faster-whisper (CPU and CUDA) as default, and a whisper.cpp CLI adapter. Analysis on a mono 16 kHz derivative, with conservative VAD.
- Versioned profanity data file (`term, language, variants, category, severity, exceptions`), tiers 1 mild, 2 strong, 3 explicit/severe, with tags such as slurs, blasphemy, sexual, bodily. Unicode and apostrophe normalization, inflections, multiword phrases, no raw substring matching.
- Canonical JSON timeline with provenance (source, evidence, word text, confidence).
- Filter profile in TOML with per-category `min_severity` and `action`, plus manual per-occurrence overrides.
- Initial mute padding of 80–150 ms before and 100–200 ms after, tuned by listening tests. Flag unaligned words and implausible timings for review.
- Default output: edited MP4 beside the source (`<name>.angel.mp4`).
- Optional exports: `--edl kodi|mplayer` (separate writers) and `--json` timeline.
- Render (default): ffmpeg audio re-encode with video stream copy; mute and bleep (about 1 kHz tone, short fades, configurable level). Every output channel muted over each interval. Explicit policy for each retained audio track.
- Batch mode over a folder, with a per-file report of unsupported tracks.
- Resumable cache keyed by media, model, and config fingerprints.
- `angel doctor`: ffmpeg/ffprobe, hardware, model availability, runtime compatibility.
- Explicit, checksummed model downloads.

**Out of scope**
- Any visual detection, skip or blur actions that need video cuts, bitmap subtitle OCR (PGS/VobSub), source separation, WhisperX, diarization.
- mpv support (no adapter yet), Plex/Jellyfin integration.
- DRM handling of any kind, and any downloading.
- Cloud services.

**Done when**
- Profane-word recall, leaked syllables, and excess muted duration are measured on the test set and reported per backend. Targets are set after the baseline run. The default backend and padding are chosen from those numbers.
- Boundary error (start and end, in ms) is reported for subtitle-aligned and ASR-aligned events.
- Reports also include runtime and peak memory per preset.
- Rendered output keeps video byte-for-byte unchanged (stream copy), keeps duration within one audio frame of the source, and has no audible profanity in the test clips when listened to on all channels.
- Exported Kodi and MPlayer EDLs are loaded and checked in the real players.
- A season folder runs end to end in batch mode. A second run reuses the cache.
- `angel doctor` correctly reports a missing ffmpeg and a missing model on a clean machine.
- Installation is tested from a built package on each supported platform.

## v1: visual detection

**Implementation status:** shipped per SPEC-v1: ContentDetector shot snapping, configurable
2 fps sampling and 8 fps candidate refinement, NudeNet exposed classes, pluggable
OpenCLIP violence classifier, visual profiles and flag/skip actions, source-time
mute/cut reconciliation, libx264 CRF 18 cut rendering, JSON schema 2 and cut/mute
EDLs, scan JSON files, season batching, and content/model/fps score caches. Core
install remains lightweight; heavy detectors are mocked in CI. No-cut rendering
retains the v0 video-copy path. Cut rendering retains primary video and audio;
subtitle/chapter remapping, annotated-film benchmarks, real-player verification,
and the broader category/model research listed below remain open. The following
scope describes those broader research goals, not additional shipped promises.

**Goal.** Generate reviewable skip ranges for nudity, sexual content, and violence as candidates, without claiming certainty.

**Scope**
- Shot detection with PySceneDetect (`AdaptiveDetector`) on a downscaled stream. TransNetV2 stays optional.
- Base sampling at about 2 fps, plus one representative frame per shot the grid misses.
- NudeNet candidates (320n default, 640m option). Independent categories for nudity, sexual activity, violence, visible blood, and gore; never merged.
- Violence candidates from temporal models, with XD-Violence-trained models evaluated first, and optional blood signal (for example BloodshotNet). CLIP-style prompt ranking evaluated as a cheap candidate ranker.
- Adaptive resampling: candidates and neighbors re-sampled at 8–12 fps, short sequences for action. Boundaries expanded, padded, and merged into scene ranges with minimum durations.
- Scene-range review output (timeline plus a way to preview and accept or reject ranges). This is v1's review mechanism; a full UI is later.
- Skip action in exports and a full re-encode render path for cuts, with synchronized A/V trim and concat, subtitle and chapter remapping through the retained-interval map.
- A strict high-recall mode with denser sampling.
- New extra such as `[vision]`.

**Out of scope**
- Severity grading by VLM, generated content, hosted services, a graphical UI, HDR-perfect output guarantees (HDR and channel layouts are explicit capabilities only).

**Done when**
- Visual-event recall and false skipped seconds per hour are measured per category on the test set, at the default and the strict mode. Targets are set after the baseline.
- Known error classes are tested and documented: swimwear, medical scenes, sculpture, animation, dark scenes, red liquids, sports, weapons without violence.
- Brief exposure (about 0.2 s) detection is measured at default sampling, and the limit is stated in the docs.
- Boundary error of merged ranges is reported.
- Rendered cuts keep A/V sync across multiple cuts, and final duration matches the retained-interval map.
- Runtime and peak memory for a 45-minute episode are published for CPU and GPU.

## v2: generative scene replacement (official target)

**Goal.** After v1's visual detection cuts a violent or nude scene, a video generative model fills the removed section with a toned-down version of the same event, so the story still makes sense and nothing jumps.

**How it works**
- The model gets the frames just before the cut and the frames just after it, so the fill matches the film's look, lighting, and characters.
- It also gets a text description of what originally happened in the scene, rewritten to communicate the same event in a less grotesque way (for example, "the attacker is struck down" instead of a graphic depiction).
- The generated clip replaces the removed section in the edited MP4.

**Target.** A working demonstration on a few sample clips. Justice will provide the sample clips.

**Legal caveat.** Generated replacement footage is added content in a fixed copy. It falls clearly outside the Family Movie Act and is private-use only, at the user's responsibility. A legal review is an open item before this ships. Hosted providers receive frames from the film, and their terms and safety filters apply.

**Building blocks (from research)**
- First/last-frame video models: local Wan FLF2V, or a hosted model (Veo, Kling, Luma) with the user's own key.
- A scene-description step (VLM or transcript) that produces the softened prompt; the prompt is saved in the timeline for review.
- Fallback chain when generation fails quality gates: interpolation, then cross-dissolve with room tone, then hard cut. A render always completes.
- Generated output is re-checked with the v1 detectors.

**Out of scope**
- Generated dialogue, voice cloning, or score; sharing generated clips.

**Done when**
- Justice's sample clips each produce an edited MP4 where the removed scene is replaced by a generated, toned-down bridge that matches the surrounding footage.
- The softened descriptions and generation settings are recorded per clip.
- Re-detection finds no flagged content in accepted fills.

## v3: optional AI severity grading

**Goal.** Reduce false positives and make thresholds feel human by grading flagged segments with a vision-language model.

**Scope**
- Grade only v1 candidates, with short timestamped frame sequences plus nearby transcript.
- Backends: local Qwen3-VL (4B/8B) and InternVL3.5, and a hosted provider with the user's own key. Benchmark before choosing defaults.
- Schema-constrained output (`category`, `severity`, `evidence_frames`, `reason`, `uncertain`). Self-reported confidence is treated as uncalibrated.
- Refusal, malformed output, or missing evidence becomes `unknown`, and `unknown` is never treated as safe: it keeps the v1 action or goes to review.
- Deterministic sampling refines boundaries; generated timestamps are not trusted directly.
- Minimal frames per request, a spending cap, and provider and model version recorded in the timeline. Opt-in per feature.
- New extra such as `[vlm]`.

**Out of scope**
- Sending whole files, grading without a v1 candidate, treating VLM output as ground truth, scene replacement.

**Done when**
- On the test set, false skipped seconds per hour drop against v1-only at equal or better visual-event recall. Both are reported.
- The rate of `unknown` results and their handling are reported per backend.
- Tests show a refusal and a malformed response each produce `unknown`, not a pass.
- Cost per 45-minute episode and local runtime and memory are measured, not estimated.
- No data leaves the machine unless the user enabled the feature, and the request payload is inspectable.

## Later

- Review UI.
- Shareable filter profiles (profiles only, never media).
- Series mode that reuses recurring intros and characters across episodes.
- mpv adapter for muting, and Plex/PlexAutoSkip export if client support is confirmed.
- WhisperX precision backend; Qwen3-ASR and Parakeet benchmarks; center-channel and source-separation experiments for difficult mixes.
- Bitmap subtitle OCR; hybrid smart rendering (re-encode only cut boundaries).
- Importing third-party timelines, bound to an edition fingerprint.

## Open questions to verify

From the research, not yet resolved:

1. The statutory text of 17 U.S.C. §110(11), especially on fixed copies and added content. A legal review before render and generate features ship.
2. Real accuracy of each speech backend on film dialogue, music, and crosstalk; published speed figures do not cover boundary accuracy. Apple Silicon needs its own benchmark.
3. Whether whisper.cpp word timestamps are accurate enough for muting; its approaches are partly experimental.
4. Whether a violence model exists that matches parental-filter categories. XD-Violence labels do not include a gore scale.
5. Sampling density needed for acceptable recall of brief exposures.
6. Whether Qwen3-VL and InternVL3.5 grade severity reliably on short sequences, and how often they refuse.
7. Vendor pricing and duration limits for hosted video and VLM APIs; the research used third-party figures.
8. Keyframe conditioning support in LTX-Video and HunyuanVideo, and the VRAM needed for Wan FLF2V.
9. Whether VidAngel's filtering service and SkipIt are currently operating.
10. Whether an active open-source project already combines local analysis with EDL output (GitHub not checked).
11. Reliable mute support in mpv and in native Plex/Jellyfin clients.
12. Code and weight licenses of every model and word list before bundling or recommending them.
