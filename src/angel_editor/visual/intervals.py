from dataclasses import dataclass

from .shots import snap


@dataclass
class VisualEvent:
    start_us: int
    end_us: int
    category: str
    score: float
    source: str
    labels: list[str]
    action: str


def merge(spans, gap=0):
    result = []
    for a, b in sorted(spans):
        if b <= a:
            continue
        if result and (a <= result[-1][1] or a - result[-1][1] < gap):
            result[-1] = (result[-1][0], max(b, result[-1][1]))
        else:
            result.append((a, b))
    return result


def events_from_scores(scores, category, rule, duration, cuts, source, fps=8, snap_window=0.75):
    hits = [s for s in scores if s.category == category and s.score >= rule["threshold"]]
    spans = merge([(s.t, min(duration, s.t + 1 / fps)) for s in hits], 1)
    result = []
    for a, b in spans:
        evidence = [s for s in hits if a <= s.t < b]
        a, b = snap(
            max(0, a - rule["pad_before"]), min(duration, b + rule["pad_after"]), cuts, snap_window
        )
        a, b = max(0, a), min(duration, b)
        if b - a >= rule["min_duration"]:
            result.append(
                VisualEvent(
                    round(a * 1e6),
                    round(b * 1e6),
                    category,
                    max(s.score for s in evidence),
                    source,
                    sorted({label for s in evidence for label in s.labels}),
                    rule["action"],
                )
            )
    return result


def combine(audio, visual):
    skips = merge([(e.start_us, e.end_us) for e in visual if e.action == "skip"])
    # Subtract cuts, retaining mute fragments that still exist in the output.
    mutes = []
    for a, b in audio:
        cursor = a
        for x, y in skips:
            if y <= cursor or x >= b:
                continue
            if cursor < x:
                mutes.append((cursor, x))
            cursor = max(cursor, y)
        if cursor < b:
            mutes.append((cursor, b))
    return merge(mutes), skips
