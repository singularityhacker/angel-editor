import importlib.util
import tempfile
from pathlib import Path

from . import cache
from .matching import match
from .media import extract_audio, run
from .speech import WhisperTranscriber
from .subtitles import parse


def analyze(path, info, settings, profile=None, transcriber=None):
    identity = cache.fingerprint(path)
    duration = round(float(info["format"]["duration"]) * 1e6)
    cues = None
    subs = settings["subs"]
    if subs != "off":
        candidates = (
            [Path(subs)]
            if subs != "auto"
            else [path.with_suffix(suffix) for suffix in (".srt", ".vtt", ".en.srt")]
        )
        found = next((p for p in candidates if p.exists()), None)
        if found:
            cues = parse(found.read_text(encoding="utf-8-sig"))
        elif subs != "auto":
            raise ValueError(f"Subtitle file not found: {subs}")
        else:
            for stream in info["streams"]:
                if stream["codec_type"] == "subtitle" and stream["codec_name"] in {
                    "subrip",
                    "ass",
                    "ssa",
                    "webvtt",
                    "mov_text",
                    "text",
                }:
                    cues = parse(
                        run(
                            [
                                "ffmpeg",
                                "-v",
                                "error",
                                "-i",
                                str(path),
                                "-map",
                                f"0:{stream['index']}",
                                "-f",
                                "srt",
                                "-",
                            ]
                        )
                    )
                    break
    available = transcriber is not None or importlib.util.find_spec("faster_whisper") is not None
    can_asr = settings["asr"] != "off" and available
    backend = transcriber or WhisperTranscriber()
    warnings = []

    def speech(start=None, end=None):
        key = f"{identity}:{settings['model']}:{settings['language']}:{start}:{end}"

        def produce():
            with tempfile.TemporaryDirectory() as directory:
                wav = Path(directory) / "audio.wav"
                extract_audio(path, wav, start, end)
                words = backend.transcribe(
                    str(wav), model=settings["model"], language=settings["language"]
                )
                for word in words:
                    word.start_us += start or 0
                    word.end_us += start or 0
                return words

        return cache.transcript(key, produce, not settings["no_cache"])

    def detect(words, source):
        return match(words, settings["strictness"], profile, source, settings["mode"])

    if cues is not None:
        events = []
        for cue in cues:
            matches = detect([cue], "subs")
            if not matches:
                continue
            aligned = []
            if can_asr:
                try:
                    aligned = detect(
                        speech(
                            max(0, cue.start_us - 1_000_000), min(duration, cue.end_us + 1_000_000)
                        ),
                        "subs",
                    )
                except (RuntimeError, ValueError) as error:
                    warnings.append(f"Subtitle alignment failed: {error}")
            if aligned:
                events.extend(aligned)
            else:
                for event in matches:
                    event.accuracy = "cue"
                events.extend(matches)
                warnings.append("accuracy: cue; muting whole subtitle cue without word alignment")
    else:
        if not can_asr:
            raise ValueError("No subtitles available; install angel-editor[speech] and enable ASR")
        events = detect(speech(), "asr")
    # Clamp event evidence independently of render padding.
    for event in events:
        event.start_us = max(0, min(duration, event.start_us))
        event.end_us = max(event.start_us, min(duration, event.end_us))
    return identity, events, list(dict.fromkeys(warnings))
