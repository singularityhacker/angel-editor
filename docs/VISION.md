# Angel Editor: Vision

## What it is
Angel Editor is an open-source, local-first CLI for filtering video you already own: language, nudity and sexual content, violence, and whatever else you choose. It works like VidAngel or SkipIt, except that everything runs on your own machine against your own files. No streaming service, crowdsourced skip list, or third party ever sees what you watch.

You bring your own API keys for the optional AI features. The core works offline.

## Who it's for and the boundaries
- People filtering media **they have purchased**, for **private, personal viewing**.
- It is not for redistribution. Angel Editor never uploads, shares, or publishes media. It doesn't break DRM. You point it at files you already have and are entitled to edit for your own use.
- (In the US, the Family Movie Act of 2005 protects making private viewing filters for lawfully owned copies. Check your own jurisdiction.)

## How it works (the pipeline)
1. **Analyze.** Scan an episode and produce a timeline of *events*: a profane word at 12:03.4–12:03.9, a nude scene from 31:10 to 31:42, and so on. Each event gets a category, a severity, and a confidence score.
2. **Decide.** Apply your *filter profile*, with per-category thresholds like VidAngel's levels (for example: language set to "mute strong profanity", nudity set to "skip all", violence set to "skip only graphic"). This turns events into *actions*: mute, bleep, skip, blur, or (later) replace.
3. **Render.**
   - *Edited copy (default):* MP4 in, clean MP4 out. ffmpeg writes a new file next to the original with the filtered audio re-encoded and the video stream-copied, so picture quality is identical and it plays in any player. The original is never modified.
   - *Sidecar export (optional):* `--edl kodi|mplayer` writes a player-specific skip/mute file and `--json` writes the full event timeline, for people who prefer filtering at playback time.
4. **Review.** The JSON timeline is plain text you can inspect and hand-tune before rendering.

## Progressive elaboration (roadmap)
- **v0, language filtering that works.** Transcribe locally with Whisper (word-level timestamps), match against a configurable word list with severity tiers, and mute or bleep exactly those words. Use existing subtitles as a fast path when they're present. Output a clean edited MP4 by default, with optional EDL/JSON export. Batch over a whole season folder.
- **v1, visual detection.** Detect shots, sample frames per shot, and run local classifiers (nudity and sexual content, violence and gore) with thresholds per category. Merge detections into scene-level skip ranges, with padding and minimum durations.
- **v2, generative scene replacement (official target).** After v1 cuts a violent or nude scene, a video generative model fills the gap. It gets the frames before and after the cut to match the style, plus a description of what originally happened, rewritten to communicate the same event in a less grotesque way. The goal is a working demo on a few sample clips Justice will provide.
- **v3, smarter judgment with AI.** Optionally send flagged segments to a vision-language model (your own key, or a local model) to grade severity and context ("a kiss" vs "a sex scene"). This cuts false positives and makes thresholds feel human.
- **Later:** a review UI, shareable filter profiles (profiles only, never media), and a series mode that reuses recurring intros and characters across episodes.

## Principles
- **Private by default.** It's local first, and cloud AI is opt-in per feature, sending the minimum (frames or short clips, never whole files).
- **Never touch the original.** The default is a new edited copy beside the source; sidecar filter files are an optional export. (Legal note: the Family Movie Act clearly covers playback-time filtering; a saved edited copy for personal use of a file you own is a grayer area. See docs/research.)
- **Transparent.** Every action is explainable: what was detected, by what, with what confidence, and which rule fired.
- **Your thresholds, not ours.** Profiles are plain config.

## Format
A Python CLI. Python has the best ecosystem for this work (Whisper, PySceneDetect, PyTorch/ONNX classifiers, ffmpeg bindings), and it's easy for others to install with `pipx` or `uv`.
