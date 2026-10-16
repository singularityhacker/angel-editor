from dataclasses import dataclass


@dataclass
class Word:
    start_us: int
    end_us: int
    word: str
    confidence: float = 1.0


@dataclass
class Event:
    start_us: int
    end_us: int
    word: str
    term: str
    severity: int
    category: str
    source: str
    confidence: float
    action: str = "mute"
    accuracy: str = "word"


def intervals(events, duration_us, before=100_000, after=150_000):
    spans = sorted(
        (max(0, e.start_us - before), min(duration_us, e.end_us + after)) for e in events
    )
    merged = []
    for start, end in spans:
        if end <= start:
            continue
        if merged and start - merged[-1][1] < 50_000:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged
