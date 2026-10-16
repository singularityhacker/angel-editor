import html
import re

from .schema import Word

STAMP = r"(?:\d+:)?\d{2}:\d{2}[.,]\d{3}"


def timestamp(value):
    parts = value.replace(",", ".").split(":")
    seconds = float(parts[-1]) + 60 * int(parts[-2])
    if len(parts) == 3:
        seconds += 3600 * int(parts[0])
    return round(seconds * 1_000_000)


def parse(text):
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        timing = re.search(rf"({STAMP})\s*-->\s*({STAMP})[^\n]*\n(.*)", block, re.DOTALL)
        if timing:
            start, end, body = timing.groups()
            if timestamp(end) <= timestamp(start):
                raise ValueError("Subtitle cue has invalid timestamps")
            cues.append(
                Word(
                    timestamp(start),
                    timestamp(end),
                    html.unescape(re.sub(r"<[^>]+>", "", body)).strip(),
                )
            )
    if not cues and text.strip() not in ("", "WEBVTT"):
        raise ValueError("No valid subtitle cues found")
    return cues
