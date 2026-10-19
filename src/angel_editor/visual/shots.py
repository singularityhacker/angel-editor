def detect_shots(path):
    from scenedetect import ContentDetector, detect

    return sorted(
        {cut.get_seconds() for scene in detect(str(path), ContentDetector()) for cut in scene}
    )


def snap(start, end, cuts, window=0.75):
    def nearest(t):
        cut = min(cuts, key=lambda c: abs(c - t), default=t)
        return cut if abs(cut - t) <= window else t

    a, b = nearest(start), nearest(end)
    return (a, b) if b > a else (start, end)
