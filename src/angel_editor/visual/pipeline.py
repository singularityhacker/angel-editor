import hashlib
import importlib.util
import json
from dataclasses import asdict

from .. import cache
from .detectors import FrameScore, NudityDetector, ViolenceDetector
from .intervals import events_from_scores
from .profiles import resolve
from .sampler import refine, sample_frames
from .shots import detect_shots


def missing_extras():
    return [
        name
        for name in ("scenedetect", "cv2", "nudenet", "open_clip", "torch")
        if importlib.util.find_spec(name) is None
    ]


def available():
    return not missing_extras()


def analyze_visual(path, duration, settings, profile=None, detectors=None):
    rules = resolve(settings.get("strictness", "moderate"), profile, settings)
    if settings.get("no_visual"):
        return []
    if detectors is None and not available():
        return []
    try:
        if detectors is None:
            detectors = {}
            if rules["nudity"]["enabled"]:
                detectors["nudity"] = NudityDetector()
            if rules["violence"]["enabled"]:
                detectors["violence"] = ViolenceDetector(settings.get("violence_model", "ViT-B-32"))
        cuts = detect_shots(path)
    except (ImportError, OSError) as error:
        raise RuntimeError(
            "Visual dependencies failed to load; install angel-editor[visual] and run angel doctor"
        ) from error
    identity = cache.fingerprint(path)
    events = []
    fps, dense = settings.get("sample_fps", 2), settings.get("dense_fps", 8)
    for category, detector in detectors.items():
        rule = rules[category]
        if not rule["enabled"]:
            continue
        key = json.dumps(
            [
                "visual-v1-stream640",
                category,
                identity,
                detector.model_id,
                fps,
                dense,
                rule["review_threshold"],
            ]
        )
        target = cache.directory() / (hashlib.sha256(key.encode()).hexdigest() + ".visual.json")
        scores = None
        if not settings.get("no_cache") and target.exists():
            try:
                scores = [FrameScore(**s) for s in json.loads(target.read_text())]
            except (ValueError, TypeError):
                pass
        if scores is None:
            scores = detector.detect(sample_frames(path, fps))
            scores = refine(path, detector, scores, rule["review_threshold"], duration, dense)
            if not settings.get("no_cache"):
                import tempfile

                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as f:
                    json.dump([asdict(s) for s in scores], f)
                from pathlib import Path

                Path(f.name).replace(target)
        events.extend(
            events_from_scores(
                scores,
                category,
                rule,
                duration,
                cuts,
                detector.model_id,
                dense,
                settings.get("snap_window", 0.75),
            )
        )
    return events
