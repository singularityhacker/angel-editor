# Angel Editor: detection and rendering research

*Research date: October 16, 2026. Read [docs/VISION.md](../VISION.md). No files modified. Performance figures below distinguish published benchmarks from planning estimates.*

**Recommendation:** build v0 around subtitle-assisted transcription, local word alignment, configurable profanity rules, and audio-only rendering. For v1, add shot detection and visual classifiers as a candidate-generation pipeline with reviewable intervals. Keep a canonical JSON timeline: player EDL formats cannot preserve categories, confidence, provenance, or every action.

## 1. Speech detection and profanity timing

### Backend choices

| Backend | Strengths | Hardware and timing implications | Recommendation |
|---|---|---|---|
| **faster-whisper** | Mature Python integration; quantization, batching, VAD, word timestamps | CPU INT8 and NVIDIA CUDA; its standard backend does not provide Apple Metal acceleration | Default CPU/CUDA backend. Start with `small` for speed; offer `large-v3`/`turbo` quality presets |
| **WhisperX** | Adds forced phoneme alignment to transcription; useful for precise word boundaries | Extra alignment model and dependencies; language-specific alignment; overlapping speech remains difficult | Optional precision backend; diarization unnecessary for ordinary muting |
| **whisper.cpp** | Lightweight native runtime; quantized models; Metal/Core ML support | Strong Apple Silicon deployment option. Word timestamp functionality includes experimental approaches; validate boundaries independently | Invoke its CLI through an adapter |
| **Qwen3-ASR + ForcedAligner** | Released January 2026; 0.6B/1.7B ASR and separate 0.6B alignment model; speech/music/song support | ASR covers 52 languages/dialects; aligner covers 11 languages. Throughput claims use batching and should not be treated as laptop latency | Benchmark as a newer alternative, especially for difficult music and multilingual material |
| **Parakeet TDT 0.6B v3** | Multilingual recognition with native character, word, and segment timestamps | NeMo integration favors a substantial PyTorch environment; alternate runtimes require separate validation | Benchmark against Whisper before choosing a second supported engine |

Sources: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [WhisperX](https://github.com/m-bain/whisperX), [whisper.cpp](https://github.com/ggml-org/whisper.cpp), [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR), [Parakeet model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3).

**Published speed reference:** faster-whisper’s benchmark transcribes 13 minutes using large-v2 on an RTX 3070 Ti in 63 seconds FP16, or 17 seconds with batch size eight. Small INT8 on an i7-12700K takes 102 seconds, or 51 seconds batched. Simple scaling gives approximately **3.6/1.0 minutes GPU** and **5.9/2.9 minutes CPU** for 45 minutes. These are different models and exclude the complete filtering pipeline; they do not establish film-dialogue accuracy or word-boundary performance. Apple Silicon needs a separate benchmark. [Benchmark configuration](https://github.com/SYSTRAN/faster-whisper#benchmark).

### Accuracy and difficult audio

Measure **profane-word recall and audible leakage**, not just overall word error rate. An otherwise excellent transcript can omit the one word being filtered.

Recommended processing:

1. Select the intended audio language/track explicitly; preserve its offset relative to the video timeline.
2. Analyze a mono 16 kHz derivative while retaining the original audio for output.
3. Use conservative VAD, retaining context around speech. Music can produce hallucinations, and sung profanity may be excluded by aggressive speech gating.
4. Align detected words; initially pad mute intervals by **80–150 ms before and 100–200 ms after**, then tune against listening tests.
5. Flag unaligned words, conflicting transcripts, and implausible timings for review.

Forced alignment places supplied words in audio; it does not prove that those words were spoken. WhisperX explicitly documents overlapping-speech and alignment limitations. Speaker diarization does not separate simultaneous voices. [WhisperX limitations](https://github.com/m-bain/whisperX#limitations).

For difficult mixes, experimentally compare a full downmix with the center channel where available. Dialogue may also occupy other channels. Optional source separation can aid recognition, but **mute every output channel** over the resulting interval; otherwise profanity can remain audible.

### Subtitles as a fast path

Use embedded text subtitles and matching `.srt`, `.vtt`, or `.ass` sidecars before full ASR:

- Validate language, edition, duration, and synchronization.
- Match profanity in subtitle text.
- Force-align only matching cues plus neighboring audio context.
- If alignment fails, offer whole-cue muting with an explicit accuracy warning in the review output.
- Treat bitmap PGS/VobSub as requiring OCR; defer that path.

Ordinary subtitle cue timestamps are sentence-level, not word-level. Captions can paraphrase, omit background speech, or censor words. Consequently, subtitle-only analysis should be labeled as such, with optional full-audio verification. [cleanvid](https://github.com/mmguero/cleanvid) is a useful existing implementation to study for subtitle-driven filtering and exports.

### Profanity vocabulary and severity

Use a versioned data file with:

```text
term, language, variants, category, severity, exceptions
```

[dsojevic/profanity-list](https://github.com/dsojevic/profanity-list) already provides severity, tags, and exceptions; [Surge AI’s dataset](https://github.com/mod-tc/profanity) includes categories and human severity ratings. [LDNOOBW](https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words) supplies multilingual vocabulary but needs a policy layer.

Suggested tiers: **1 mild, 2 strong, 3 explicit/severe**, with independent tags for slurs, blasphemy, sexual references, and bodily language. These are editable product definitions, not universal ratings.

Normalize Unicode, case, apostrophes, and tokenization; support inflections and multiword phrases. Avoid unrestricted substring matching. Preserve original words and evidence in the timeline.

### Mute versus bleep

- **Mute:** replace original audio with silence during the interval; removes music and effects too.
- **Bleep:** mute first, then mix a bounded tone, initially around 1 kHz with short fades and configurable level.
- Mute is quieter and simpler; bleep makes the edit apparent but can become distracting.

Illustrative mute-only command:

```bash
ffmpeg -i input.mkv -map 0:v:0 -map 0:a:0 \
  -c:v copy -af "volume=0:enable='between(t,723.32,723.95)'" \
  -c:a aac output.mkv
```

FFmpeg’s timeline-enabled volume filter operates at audio-frame granularity. For precise production output, split at sample boundaries with `atrim`, apply ramps, and concatenate; generate filtergraphs programmatically. [FFmpeg audio filters](https://ffmpeg.org/ffmpeg-filters.html#Audio-Filters).

## 2. Visual detection

### Models and their roles

| Component | Suitable role | Main limitation |
|---|---|---|
| **PySceneDetect** | Default CPU shot-boundary pass; `AdaptiveDetector` accommodates changing frame differences | Motion, flashes, fades, and rapid editing require tuning; shots are not semantic scenes |
| **TransNetV2** | Optional learned shot-transition detector | Adds model/runtime complexity; benchmark gains do not establish better content filtering |
| **NudeNet** | Detect exposed anatomy with boxes and scores; default 320n, larger 640m option | Anatomy detection does not determine sexual activity, context, or severity |
| **Violence models** | Temporal candidate scores from action/anomaly models | Dataset labels often differ substantially from parental filtering categories |
| **BloodshotNet** | Additional blood candidate signal | Blood presence is neither sufficient nor necessary for graphic violence |
| **CLIP/OpenCLIP-style models** | Cheap configurable candidate ranking using text prompts | Similarity scores are not calibrated probabilities; single frames miss actions |
| **Local VLM** | Context and severity grading of short candidate sequences | Slower, memory-intensive, prompt-sensitive; may hallucinate or refuse |

Sources: [PySceneDetect](https://www.scenedetect.com/docs/latest/), [TransNetV2](https://github.com/soCzech/TransNetV2), [NudeNet](https://github.com/notAI-tech/NudeNet), [BloodshotNet](https://github.com/wearebit/BloodshotNet), [CLIP model card](https://github.com/openai/CLIP/blob/main/model-card.md).

For violence, investigate temporal models trained on **XD-Violence**, whose movie/YouTube material is more relevant than purely surveillance footage. Its labels include fighting, shootings, and explosions; it does not provide a ready-made “graphic gore” scale. UCF-Crime includes surveillance anomalies such as burglary and shoplifting, further illustrating the taxonomy mismatch. [XD-Violence paper](https://arxiv.org/abs/2007.04687), [UCF-Crime dataset](https://www.crcv.ucf.edu/research/real-world-anomaly-detection-in-surveillance-videos/).

**Do not conflate:** nudity, sexual activity, violence, visible blood, and gore. Maintain independent categories. Expected errors include swimwear, medical procedures, sculptures, animation, dark scenes, small subjects, red liquids, sports, and weapons without actual violence.

### Local versus hosted severity grading

Benchmark **Qwen3-VL 4B/8B** and **InternVL3.5** on short timestamped frame sequences plus nearby transcript. Qwen3-VL supports video inputs and temporal grounding. A quantized 8B model has roughly 4 GB of raw four-bit weights, but runtime memory also includes the vision encoder, caches, and activations. [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL), [InternVL3.5 report](https://arxiv.org/abs/2508.18265).

Request schema-constrained output:

```json
{
  "category": "violence.gore",
  "severity": 3,
  "evidence_frames": [1281.5, 1282.0],
  "reason": "visible traumatic injury",
  "uncertain": false
}
```

Treat self-reported confidence as uncalibrated. Refusal, malformed output, or missing evidence becomes **unknown**, never “safe.” Let deterministic sampling refine boundaries rather than accepting generated timestamps directly.

Hosted VLM APIs can simplify deployment and offer larger models. Gemini documents native video processing; frame-sequence APIs are another option. Keep cloud grading optional, send only selected evidence, record provider/model versions, and cap spending. Sparse sampling remains a limitation regardless of hosting. [Gemini video processing](https://ai.google.dev/gemini-api/docs/video-understanding).

### Sampling and cost per episode

**Proposed starting strategy, not a proven recall guarantee:**

1. Decode sequentially; perform shot detection on a downscaled stream.
2. Sample **2 fps**, plus a representative frame from every shot that the grid misses.
3. Batch cheap detectors; use thresholds tuned for candidate recall.
4. Resample candidates and adjacent context at **8–12 fps**; use short frame sequences for action assessment.
5. Expand confirmed boundaries, apply modest padding, and merge overlapping intervals.

A 0.2-second exposure can fall entirely between 2 fps samples. A strict high-recall mode needs substantially denser coverage, potentially every frame.

For a **45-minute episode**:

| Work | Planning calculation |
|---|---|
| Base visual pass | 5,400 frames plus shot representatives |
| Classifier time | At measured aggregate 20/100 frames per second: **4.5 minutes / 54 seconds**, excluding decoding |
| VLM grading | 60 candidates × 3 seconds per request: **3 minutes**; CPU could be much slower |
| Local inference charges | $0 API fees; electricity and hardware remain |
| Hosted grading example | 600,000 input + 20,000 output tokens at $0.10/$0.40 per million: **$0.068** |

The hosted example uses published **Gemini 2.5 Flash-Lite** rates, not an assurance that this model grades severity adequately. Whole-video static processing at 258 visual tokens/second yields about 697,000 visual tokens for 45 minutes, before audio, metadata, and output. Actual image tokenization, resolution, retries, and model choice change cost. [Pricing](https://ai.google.dev/gemini-api/docs/pricing), [video token accounting](https://ai.google.dev/gemini-api/docs/video-understanding#technical-details-video).

## 3. Profiles, skip lists, and interoperability

### Category and threshold behavior

VidAngel exposes categories, subcategories, individual words, and individual occurrences; its controls are richer than one global severity slider. Skipit describes community-submitted, voted timestamp ranges with automatic skipping. These are different annotation workflows feeding similar playback actions. [VidAngel filters](https://help.vidangel.com/hc/en-us/articles/360055496752-What-Filters-options-do-you-provide), [Skipit](https://getskipit.com/).

For Angel Editor, define explicit semantics:

```toml
[language]
min_severity = 2
action = "mute"

[nudity]
min_severity = 1
action = "skip"

["violence.gore"]
min_severity = 3
action = "skip"
```

Apply actions when `severity >= min_severity`. Keep **severity**, **detector confidence**, and **review status** separate. Manual occurrence overrides take priority; skip takes priority over mute within overlapping intervals.

Bind imported timelines to an edition fingerprint, duration, and selected tracks. A title match is insufficient: recaps, logos, alternate cuts, and frame-rate conversions shift timestamps.

### Projects and formats worth studying

| Project/format | Reuse or interoperability opportunity |
|---|---|
| [MPlayer EDL](https://mplayerhq.hu/DOCS/HTML/en/edl.html) | `start end action`; action `0` skips, `1` mutes |
| [Kodi EDL](https://kodi.wiki/view/Edit_decision_list) | Same-stem sidecars; cut/mute plus scene-marker and commercial-break extensions |
| [mpv EDL](https://github.com/mpv-player/mpv/blob/master/DOCS/edl-mpv.rst) | Separate format describing retained source segments and a virtual timeline |
| [sensible-cinema](https://github.com/rdp/sensible-cinema) | Historical open-source family-filtering player and delete-list tooling |
| [cleanvid](https://github.com/mmguero/cleanvid) | Subtitle profanity workflow; EDL and PlexAutoSkip JSON exports |
| [PlexAutoSkip](https://github.com/mdhiggins/PlexAutoSkip) | Custom skip intervals; client-control compatibility must be checked |
| [jellyfin-whisper](https://github.com/electrovir/jellyfin-whisper) | whisper.cpp analysis, mute EDLs, and rendered clean audio tracks |

**Correct the vision’s compatibility assumption:** one `.edl` does not work identically across mpv, MPlayer, and Kodi. Export Kodi/MPlayer EDL separately. For mpv, use retained-segment EDL for cuts and a playback adapter for muting; validate seeks and buffering carefully. Native Plex/Jellyfin clients should not be assumed to consume arbitrary mute sidecars.

## 4. Rendering and A/V sync

| Method | Advantages | Constraints |
|---|---|---|
| **Playback sidecars** | Instant, reversible, no quality loss | Player support varies; seeks can expose frames; bleep/blur require additional implementation |
| **Audio re-encode, video copy** | Best v0 output for mute/bleep; preserves video | Audio changes; every retained audio track needs an explicit policy |
| **Full re-encode** | Reliable arbitrary cuts and visual effects | Compute, quality loss, HDR/color and metadata handling |
| **Stream-copy cuts** | Fast, no recompression | Safe video boundaries depend on random-access frames/GOP structure; audio packet boundaries differ |
| **Hybrid smart rendering** | Potentially re-encode only cut boundaries | Codec-specific complexity; defer |

Stream copy cannot apply filters. Input seeking generally lands at an earlier seek point; transcoding can decode and discard intervening material, whereas stream copy may preserve it. Thus arbitrary `-ss ... -c copy` is unsuitable for guaranteed exact filtering. [FFmpeg stream copy and seeking](https://ffmpeg.org/ffmpeg.html).

Recommended timeline rules:

- Store half-open intervals `[start, end)` using integer microseconds and original presentation timestamps.
- Preserve relative stream offsets; never infer time as `frame_number / nominal_fps` for variable-frame-rate video.
- Compile one ordered edit plan for all streams.
- For cuts, pair `trim`/`atrim`, reset segment timestamps, and concatenate matching A/V segments.
- Remap subtitles and chapters through the retained-interval map.
- Validate encoder delay, final duration, and sync around multiple cuts.
- Treat HDR preservation and audio channel layouts as explicit output capabilities.

FFmpeg documents timestamp-reset requirements and concatenation behavior. [Concat filter](https://ffmpeg.org/ffmpeg-filters.html#concat).

## 5. Recommended v0/v1 architecture

**v0:** probe → subtitles/ASR → word alignment → profanity matching → reviewable events → profile → EDL/audio render.

Ship CPU faster-whisper and a whisper.cpp adapter; make WhisperX optional. Include batch processing, cached analysis, manual overrides, and clear reporting of unsupported tracks.

**v1:** add shot detection, NudeNet, optional blood/temporal violence candidates, adaptive resampling, and scene-range review. Keep VLM severity grading experimental and optional, consistent with the vision’s v2 direction.

```text
src/angel_editor/
  cli.py
  schema.py              # Media, Word, Event, Action, provenance
  probe.py               # ffprobe, tracks, PTS, edition identity
  cache.py               # resumable stages, model/config fingerprints
  subtitles.py
  speech/
    base.py
    faster_whisper.py
    whisper_cpp.py
    alignment.py
  detection/
    profanity.py
    shots.py
    nudity.py
    violence.py
    vlm.py
  policy.py              # thresholds and occurrence overrides
  timeline.py            # padding, unions, conflicts, time mapping
  export/
    json.py
    kodi_edl.py
    mpv.py
    plex.py
  render/
    plan.py
    ffmpeg.py
  data/
    profanity/
```

Use `pyproject.toml`, a `src` layout, Python 3.11 initially, and extras such as `[speech]`, `[align]`, `[vision]`, and `[vlm]`. Require external `ffmpeg`/`ffprobe`; provide `angel doctor` for binaries, hardware, model availability, and runtime compatibility. Keep model downloads explicit and checksummed; inspect code and weight licenses independently.

Proposed installation commands:

```bash
uv tool install 'angel-editor[speech]'
pipx install 'angel-editor[speech]'
```

Both isolate CLI dependencies; uv also manages Python versions. Keep a development lockfile and test the packaged installation on each supported platform. [uv tools](https://docs.astral.sh/uv/guides/tools/), [pipx](https://pipx.pypa.io/stable/explanation/comparisons.html).

Before selecting defaults, benchmark a human-annotated set containing dialogue, music, crosstalk, animation, brief exposure, and graphic/non-graphic action. Report **profane-word recall, leaked syllables, excessive muted duration, visual-event recall, false skipped seconds per hour, boundary error, runtime, and peak memory**. Those measurements should determine thresholds and supported quality presets.
