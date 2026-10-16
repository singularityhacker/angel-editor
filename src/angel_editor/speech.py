from typing import Protocol

from .schema import Word


class Transcriber(Protocol):
    def transcribe(self, audio: str, *, model: str, language: str) -> list[Word]: ...


class WhisperTranscriber:
    def __init__(self):
        self.models = {}

    def transcribe(self, audio, *, model, language):
        from faster_whisper import WhisperModel

        if model not in self.models:
            self.models[model] = WhisperModel(model, device="cpu", compute_type="int8")
        segments, _ = self.models[model].transcribe(
            audio, language=language, word_timestamps=True, vad_filter=True
        )
        return [
            Word(round(w.start * 1e6), round(w.end * 1e6), w.word, w.probability)
            for segment in segments
            for w in (segment.words or [])
        ]
