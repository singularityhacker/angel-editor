import queue
import re
import subprocess
import threading
from collections import deque


def sample_frames(path, fps=2, start=0, end=None):
    """Stream bounded BGR frames with presentation timestamps; close on early exit."""
    import numpy as np

    from ..media import run

    # -copyts keeps container timestamps, which begin at start_time (e.g. 1.4 s for
    # MPEG-TS); seeks are offset by it too, so shift to and from zero-based media time.
    origin = float(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=start_time",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ]
        ).strip()
        or 0
    )
    first, last = start + origin, None if end is None else end + origin
    filters = f"select='gte(t,{first})"
    if last is not None:
        filters += f"*lt(t,{last})"
    filters += (
        f"',fps={fps},scale=w='min(640,iw)':h='min(640,ih)'"
        ":force_original_aspect_ratio=decrease,format=bgr24,showinfo"
    )
    seek = ["-ss", str(start)] if start else []
    if end is not None:
        seek += ["-to", str(end)]
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "info",
            "-nostdin",
            "-nostats",
            "-copyts",
            *seek,
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-sn",
            "-dn",
            "-vf",
            filters,
            "-vsync",
            "0",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    metadata = queue.Queue(maxsize=16)
    stopped = threading.Event()
    errors = deque(maxlen=20)

    def enqueue(item):
        while not stopped.is_set():
            try:
                metadata.put(item, timeout=0.1)
                return
            except queue.Full:
                pass

    def read_metadata():
        try:
            for raw in process.stderr:
                line = raw.decode(errors="replace")
                errors.append(line[-1000:])
                match = re.search(r"pts_time:([\d.eE+-]+).*? s:(\d+)x(\d+)", line)
                if match:
                    enqueue((float(match[1]), int(match[2]), int(match[3])))
        finally:
            enqueue(None)

    reader = threading.Thread(target=read_metadata, daemon=True)
    reader.start()
    try:
        while (item := metadata.get()) is not None:
            t, width, height = item
            size = width * height * 3
            data = bytearray()
            while len(data) < size:
                block = process.stdout.read(size - len(data))
                if not block:
                    raise RuntimeError("Incomplete sampled frame: " + "".join(errors)[-3000:])
                data.extend(block)
            t -= origin
            if t >= start and (end is None or t < end):
                yield t, np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)
        if process.wait():
            raise RuntimeError("".join(errors)[-3000:])
    finally:
        stopped.set()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        reader.join()
        process.stdout.close()
        process.stderr.close()


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
