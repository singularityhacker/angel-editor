import re
import subprocess
import tempfile
from pathlib import Path


def sample_frames(path, fps=2, start=0, end=None):
    """Decode sampled BGR frames; showinfo supplies presentation timestamps, not frame indices."""
    import cv2

    filters = f"select='gte(t,{start})"
    if end is not None:
        filters += f"*lt(t,{end})"
    filters += f"',fps={fps},showinfo"
    seek = ["-ss", str(start)] if start else []
    if end is not None:
        seek += ["-to", str(end)]
    with tempfile.TemporaryDirectory() as directory:
        result = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "info",
                "-nostdin",
                "-copyts",
                *seek,
                "-i",
                str(path),
                "-vf",
                filters,
                "-vsync",
                "0",
                str(Path(directory) / "%08d.png"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr[-3000:])
        times = [float(t) for t in re.findall(r"pts_time:([\d.eE+-]+)", result.stderr)]
        paths = sorted(Path(directory).glob("*.png"))
        if len(times) != len(paths):
            raise RuntimeError("Frame timestamp count mismatch")
        for t, frame in zip(times, paths):
            if t >= start and (end is None or t < end):
                decoded = cv2.imread(str(frame))
                if decoded is None:
                    raise RuntimeError(f"Could not decode sampled frame at {t}s")
                yield t, decoded


def refine(path, detector, scores, review, duration, dense_fps=8, sampler=sample_frames):
    windows = []
    for score in sorted(scores, key=lambda s: s.t):
        if score.score < review:
            continue
        a, b = max(0, score.t - 2), min(duration, score.t + 2)
        if windows and a <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(b, windows[-1][1]))
        else:
            windows.append((a, b))
    refined = [s for s in scores if not any(a <= s.t < b for a, b in windows)]
    for a, b in windows:
        refined.extend(detector.detect(sampler(path, dense_fps, a, b)))
    return sorted(refined, key=lambda s: s.t)
