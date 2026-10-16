# Angel Editor research: generative gap filling, legal framing, positioning

*Research only, no files modified. Prepared Oct 16, 2026. This is not legal advice. Most video-API figures come from third-party blogs and I did not confirm them against vendor pricing pages, so check those before building. Anything I couldn't confirm is marked.*

## 1. Generative gap filling (v3)

### 1.1 Classic frame interpolation
- **RIFE** is fast and multi-scale. It suits small to moderate motion and continuous shots, and the v4.2x variants are the common ones ([ComfyUI wiki](https://comfyui-wiki.com/en/models/frame-interpolation/frame-interpolation)).
- **FILM** (Google) targets large motion with a scale-agnostic bidirectional motion estimator ([paper](https://arxiv.org/pdf/2202.04901), [Google blog](https://research.google/blog/large-motion-frame-interpolation/)).
- A 2025 survey covers newer interpolation work ([AceVFI](https://arxiv.org/pdf/2506.01061)). My search found no 2026 benchmark, so I can't name a current best interpolation model.
- **Pitfall:** interpolation only works when both frames show the same scene. Across a real scene cut, with a different location, lighting and cast, it produces a ghosted cross-dissolve or morph. So it is only useful for short gaps inside a continuous shot, such as a trimmed moment between two nearly matching frames.

### 1.2 First/last-frame video models (as reported by blogs)

| Model | Access | Max clip | Rough cost | Source |
|---|---|---|---|---|
| Veo 3.1 | Hosted API | 4/6/8 s (some blogs claim 60 s, which looks wrong) | ~$0.40/s with audio at 720p/1080p; Replicate lists $0.20/s without audio | [rangy](https://rangy.ai/blog/ai-video-pricing-explained/), [mer.vin](https://mer.vin/2026/09/which-ai-video-models-actually-take-a-first-and-last-frame/) |
| Kling 3.0 | Hosted | 3–15 s | ~$0.084/s (~$0.84 per 10 s at 720p, no audio) | [rangy](https://rangy.ai/blog/veo-vs-kling-vs-runway/) |
| Runway Gen-4.5 | Hosted | ≤10 s | Credit-based; no official USD figure found | [higgsfield](https://higgsfield.ai/blog/best-ai-video-generation-apis) |
| Luma Ray 3.x | Hosted | 5–10 s | ~$0.09/s (~$0.90 per 10 s at 720p) | [crazyrouter](https://crazyrouter.com/en/blog/ai-video-generation-api-pricing-comparison-2026) |
| Wan 2.2 and later | Hosted (Alibaba, fal) | 2–10 s (Wan 2.7); kf2v-flash fixed at 5 s | ~$0.05–0.10/s | same |
| Wan 2.1 FLF2V | Local, Apache 2.0 | ~5 s at 720p | Your GPU | [HF](https://huggingface.co/Wan-AI/Wan2.1-FLF2V-14B-720P), [ComfyUI docs](https://docs.comfy.org/tutorials/video/wan/wan-flf) |
| LTX-Video, HunyuanVideo | Local | — | — | — |

- **Local VRAM:** Wan and LTX run in the 10–12 GB tier with community optimizations, but I found no official FLF2V VRAM figure ([Wan2GP](https://huggingface.co/spaces/attong39/Wan2GP/blob/main/docs/MODELS.md)). Community consensus is that LTX is much faster but lower quality, Wan is best on motion and quality, and Hunyuan is good at multi-person scenes.
- **Unconfirmed:** I found nothing on LTX or Hunyuan keyframe conditioning, so verify that before committing to either.
- **Sora:** one source says the API retires Sept 24, 2026, so don't build on it.
- **Latency:** I have no sourced figures. From experience, hosted models take roughly 1–5 minutes per clip, and local 14B models take several minutes per 5 s clip on a 24 GB GPU.
- **Cost per bridge:** a 3–5 s bridge costs about $0.25–$2 hosted. Per film that is cents to tens of dollars, even with many cuts.

### 1.3 Quality pitfalls
- **Identity drift.** Faces and clothing drift over the middle of the clip. Mitigate by keeping bridges to 2–4 s and prompting for a plausible establishing or reaction shot. Running a face-similarity check against the endpoint frames (ArcFace embeddings) gives an automatic reject signal.
- **Motion.** Models tend to fabricate smooth slow-mo or camera drift instead of matching the real motion in the footage. Pass 2–3 frames of context per side if the model supports it, or use video-to-video continuation.
- **Lighting and grade.** Color and exposure mismatch at the seams. Apply histogram or grade matching, and blend the first and last few frames with the originals.
- **Frame rate, resolution and aspect.** Generated clips come out at 24 fps and 720p, and often 16:9 only. Resample, upscale or crop to match the source, and add film grain to match.
- **Semantic trap.** A scene removed for nudity or violence can leave an unmotivated gap, and the model can generate content you wanted removed. Use a conservative prompt and run the output back through your own v1/v2 classifiers.
- **Cloud privacy.** Hosted models receive frames from the film. Make this opt-in (as the vision says), and check each provider's terms and filters. Some providers' safety filters may reject frames adjacent to mature scenes.

### 1.4 Audio bridging
Do this in tiers, cheapest first:
1. **Equal-power cross-fade**, 150–500 ms, with ffmpeg `acrossfade`.
2. **Room tone fill.** Sample 1–2 s of ambience from just before or after the cut (a low-dialogue region), loop it with cross-fades, and fade the music bed under the transition.
3. **Generative.** Use a video-model audio track (Veo produces audio) or a text-to-ambience model. Dialogue and music should not be generated, because lip-sync, voice cloning and score mismatch are all easy to notice and legally riskier.
4. **Prefer the cut point on a music or ambience beat or a sentence boundary.** Snap the cut edges using Whisper word timestamps.

### 1.5 Recommendation
- **Default (v3 baseline):** a hard cut with a short audio-video cross-dissolve (4–12 frames), room tone, and an optional black or fade-through-black transition. This needs no generation and avoids the jarring jump cut.
- **Practical generative path:** for gaps of 2–4 s where both endpoints are in the same location, make a bridge with **Wan FLF2V locally** (open license, no uploads) or **Veo 3.1 / Kling 3 / Luma via the user's own key**. Run quality gates (face-similarity, color delta, flow-continuity), and then fall back automatically.
- **Fallback chain:** FLF generation → RIFE/FILM (only if the endpoints are similar) → cross-dissolve → hard cut. Never fail the render.
- **Architecture:** use a provider-plugin interface with a mock provider for tests, and cache bridges keyed by endpoint hashes. Put the generative step behind an explicit `--bridge=generate` flag.

## 2. Legal and ethical framing

### 2.1 Family Movie Act (2005)
- It is part of the Family Entertainment and Copyright Act and is codified at 17 U.S.C. §110(11). It exempts making limited portions of a motion picture imperceptible during a private-home performance, from an authorized copy, as long as **no fixed copy of the altered version is created** ([CRS summary](https://www.everycrsreport.com/reports/RS22042.html)). I could not retrieve the statutory text; check [Cornell LII](https://www.law.cornell.edu/uscode/text/17/110).
- It also excludes **adding** audio or video content over the film (the law review notes this excluded MovieMask) ([Columbia CBLR](https://journals.library.columbia.edu/index.php/CBLR/article/view/3013)).
- It does **not** exempt DRM circumvention. DMCA §1201 still applies, and I recall the Act says so explicitly.
- Consequences for Angel Editor:
  - **Sidecar EDL/skip files used at playback** are the core case the Act was written for. This is the safe design.
  - **Rendered edited copies** create a fixed copy and fall outside the safe harbor. Private use may still be defensible on other grounds, but don't claim the Act covers it.
  - **Generated bridge clips** are added content and a fixed copy, so they are clearly outside the Act. Treat v3 as a higher-risk, user-responsibility feature.

### 2.2 VidAngel litigation
- Disney et al. sued in 2016. The Ninth Circuit affirmed the preliminary injunction, holding VidAngel unlikely to succeed on its Act defense because it did not use authorized copies, and also unlikely on fair use ([Wikipedia](https://en.wikipedia.org/wiki/VidAngel)).
- VidAngel's problem was that it decrypted discs and streamed to customers from a copy it held, which is not an authorized copy for the viewer.
- A jury awarded $62.4M, reduced to **$9.9M**, paid over 14 years, and VidAngel agreed not to decrypt or distribute Disney and Warner content. The appeal was dropped in the Sept 2020 settlement, so the Act's scope was never decided on the merits ([Christian Post](https://www.christianpost.com/news/vidangel-settles-4-year-legal-battle-with-disney-warner-brothers.html)).
- The content arm rebranded as Angel Studios and is now publicly traded. A separate entity runs the filtering business, and I could not confirm it still operates ([Wikipedia](https://en.wikipedia.org/wiki/Angel_Studios)).

### 2.3 ClearPlay
- It was the product the Act was written to protect: DVD and stream filtering using time-code files, applied at playback and with no copy made. It is subscription-based (about $7.99/month, $79.99/year, mostly through Chrome in 2026; pricing is from a review site, so verify it) ([review](https://learnofchrist.com/resources/clearplay)).
- *Clean Flicks v. Soderbergh* (D. Colo. 2006) shows the other side: companies selling physically edited copies lost.

### 2.4 What's safe and what isn't for an open-source tool

| Area | Safer | Risky |
|---|---|---|
| Source | User's own lawful copy | Pirated or streamed rips |
| DRM | Accept already-decrypted files | Bundling, linking to, or documenting ripping tools |
| Output | Sidecar EDL, played locally | Rendered copy (outside the Act's safe harbor; keep private) |
| Added content | None | Generated bridges (added content) |
| Distribution | Share filter profiles only | Sharing rendered films or bridge clips |
| Cloud AI | Opt-in, minimal frames, user's key | Uploading whole files |

- Tool authors generally face less exposure than service operators, but the **contributory/inducement** risk is real, so avoid marketing or docs that encourage infringement.
- Don't ship studio-specific skip lists with any copyrighted frames, transcripts or lengthy subtitle text. Timestamps and category labels alone are the safer distribution.
- Outside the US, check local law (for example, EU private-copy rules and moral rights).

### 2.5 Suggested README wording
> **Angel Editor** is a local-first tool for creating personal viewing filters for videos you lawfully own. It does not circumvent DRM, download, stream, or distribute media; you must supply files you are entitled to use. By default it writes a sidecar filter file (EDL) that your player applies during private playback, and the original file is never modified.
>
> *Optional features that render an edited copy or generate bridge clips go beyond what the US Family Movie Act of 2005 (17 U.S.C. §110(11)) addresses. They are intended for private use only; don't share their output. Optional cloud AI features send frames to a third party using your own API key, so check that provider's terms.*
>
> *This project is not legal advice and isn't affiliated with any studio or filtering service. Laws vary by country; you are responsible for complying with yours.*

## 3. Positioning and comparison

**Positioning.** Angel Editor is the local, inspectable, bring-your-own-files filter. VidAngel, ClearPlay and SkipIt depend on a vendor's catalog, subscription and crowdsourced skip lists tied to streaming platforms. Angel Editor analyzes files you already own on your own machine and produces plain-text filter files you can read and edit. Its filter profiles are user-controlled, it works offline, and optional AI uses your key and only the frames it needs. It does not host or ship media.

| | **Angel Editor** | **VidAngel** | **ClearPlay** | **SkipIt** |
|---|---|---|---|---|
| Model | Open-source CLI, local | Commercial service; status unconfirmed | Subscription (~$8/mo) | Startup (a Wefunder raise); not verified |
| Content source | Your own files | Streaming catalog | Streaming via extension, discs | Streaming |
| Filter data | Generated locally by you | Curated tags | Curated by the vendor | Pre-scene alerts (crowd and AI claims unverified) |
| Offline | Yes | No | Partly | No |
| Output | EDL; optional render | Streamed edit | Playback skip | Playback skip/alerts |
| Customizable | Fully (plain config) | Per-category | Per-category | Per-category |
| Privacy | Nothing leaves your machine by default | Account and viewing data on the vendor's servers | Same | Same |
| Legal posture | Private use, you own the file | Lost to the studios; paid $9.9M | Protected by the Act | Unclear |
| Gap filling | Planned (v3) | No | No | No |

Sources for the table: [ClearPlay review](https://learnofchrist.com/resources/clearplay), [Skipit on Wefunder](https://wefunder.com/skipit), [VidAngel](https://en.wikipedia.org/wiki/VidAngel).

**Open-source alternatives.**
- **VideoSkip** is a browser extension for streaming sites that mutes, skips or blanks by category, using the same categories as IMDb's Parents Guide ([AlternativeTo](https://alternativeto.net/software/vidangel)).
- **mpv and Kodi** can play EDL files, which is how the sidecar output is consumed.
- **Clean Media Player** is the closest functional match, but it is proprietary and appears discontinued.
- My search found no active open-source project that combines local Whisper/vision analysis with EDL output, which is a likely gap for Angel Editor. I haven't checked GitHub directly, so do that before claiming it.

## Open items to verify
1. The statutory text of §110(11) ([LII](https://www.law.cornell.edu/uscode/text/17/110)) and its exact language on fixed copies and added content.
2. Vendor pricing and duration limits on the official pages.
3. LTX-Video and HunyuanVideo keyframe support.
4. Whether VidAngel's filtering service and SkipIt are currently operating.
5. A legal review before shipping render or generate features.

Sources:
- [9 Best AI Video Generation APIs in 2026](https://higgsfield.ai/blog/best-ai-video-generation-apis)
- [AI Video Pricing Explained (2026)](https://rangy.ai/blog/ai-video-pricing-explained/)
- [Veo 3 vs Kling 3 vs Runway](https://rangy.ai/blog/veo-vs-kling-vs-runway/)
- [Which AI Video Models Take a First and Last Frame](https://mer.vin/2026/09/which-ai-video-models-actually-take-a-first-and-last-frame/)
- [AI Video Generation API Pricing Comparison 2026](https://crazyrouter.com/en/blog/ai-video-generation-api-pricing-comparison-2026)
- [Wan2.1 FLF2V on Hugging Face](https://huggingface.co/Wan-AI/Wan2.1-FLF2V-14B-720P)
- [Wan FLF in ComfyUI docs](https://docs.comfy.org/tutorials/video/wan/wan-flf)
- [Wan2GP model guide](https://huggingface.co/spaces/attong39/Wan2GP/blob/main/docs/MODELS.md)
- [FILM paper](https://arxiv.org/pdf/2202.04901)
- [Google FILM blog](https://research.google/blog/large-motion-frame-interpolation/)
- [AceVFI survey](https://arxiv.org/pdf/2506.01061)
- [ComfyUI frame interpolation wiki](https://comfyui-wiki.com/en/models/frame-interpolation/frame-interpolation)
- [VidAngel on Wikipedia](https://en.wikipedia.org/wiki/VidAngel)
- [Christian Post on the VidAngel settlement](https://www.christianpost.com/news/vidangel-settles-4-year-legal-battle-with-disney-warner-brothers.html)
- [Angel Studios on Wikipedia](https://en.wikipedia.org/wiki/Angel_Studios)
- [CRS report RS22042](https://www.everycrsreport.com/reports/RS22042.html)
- [Columbia Business Law Review on ClearPlay](https://journals.library.columbia.edu/index.php/CBLR/article/view/3013)
- [ClearPlay review](https://learnofchrist.com/resources/clearplay)
- [Skipit on Wefunder](https://wefunder.com/skipit)
- [AlternativeTo VidAngel alternatives](https://alternativeto.net/software/vidangel)
