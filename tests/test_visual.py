import json
import sys
import types

import pytest

from angel_editor.exports import kodi_edl, timeline
from angel_editor.visual.detectors import FrameScore, NudityDetector
from angel_editor.visual.intervals import combine, events_from_scores, merge
from angel_editor.visual.profiles import resolve
from angel_editor.visual.sampler import refine
from angel_editor.visual.shots import snap


def test_profiles_and_intervals():
    assert resolve("strict")["nudity"]["threshold"] < resolve("lenient")["nudity"]["threshold"]
    rule = resolve(profile={"nudity": {"action": "flag"}}, settings={"nudity_threshold": 0.7})[
        "nudity"
    ]
    assert rule["threshold"] == 0.7 and rule["action"] == "flag"
    with pytest.raises(ValueError):
        resolve(profile={"violence": {"threshold": 2}})
    assert merge([(0, 1), (1.9, 2)], 1) == [(0, 2)]
    assert merge([(0, 1), (2, 3)], 1) == [(0, 1), (2, 3)]
    assert snap(1.4, 3.4, [1, 3]) == (1, 3)
    scores = [FrameScore(1, "nudity", 0.9, ["exposed"])]
    events = events_from_scores(scores, "nudity", resolve()["nudity"], 5, [0.5, 1.5], "mock")
    assert (events[0].start_us, events[0].end_us) == (500000, 1500000)
    mutes, cuts = combine([(0, 2000000), (700000, 900000)], events)
    assert mutes == [(0, 500000), (1500000, 2000000)]
    assert "0.500 1.500 0" in kodi_edl(mutes, cuts)
    data = json.loads(timeline("hash", {}, events))
    assert data["schema_version"] == 2
    assert data["events"][0]["score"] == 0.9
    assert not events_from_scores(scores, "nudity", dict(rule, min_duration=10), 5, [], "mock")


def test_dense_refinement():
    calls = []

    def sampler(path, fps, start, end):
        calls.append((fps, start, end))
        return [(start + 0.25, None)]

    class Detector:
        def detect(self, frames):
            return [FrameScore(t, "nudity", 0.9, []) for t, _ in frames]

    scores = [FrameScore(3, "nudity", 0.4, []), FrameScore(4, "nudity", 0.5, [])]
    result = refine("file", Detector(), scores, 0.3, 10, sampler=sampler)
    assert calls == [(8, 1, 6)]
    assert result[0].t == 1.25 and len(result) == 1


def test_nudenet_mock(monkeypatch):
    class Model:
        def detect(self, frame):
            return [
                {"class": "BREAST_FEMALE_COVERED", "score": 0.99},
                {"class": "BREAST_FEMALE_EXPOSED", "score": 0.8},
            ]

    monkeypatch.setitem(sys.modules, "nudenet", types.SimpleNamespace(NudeDetector=Model))
    scores = NudityDetector().detect([(1, None)])
    assert scores[0].score == 0.8 and scores[0].labels == ["BREAST_FEMALE_EXPOSED"]


def test_visual_pipeline_cache(tmp_path, monkeypatch):
    from angel_editor.visual import pipeline

    monkeypatch.setenv("ANGEL_CACHE_DIR", str(tmp_path / "cache"))
    path = tmp_path / "source"
    path.write_bytes(b"synthetic media hash")
    monkeypatch.setattr(pipeline, "detect_shots", lambda path: [0, 1, 2, 3])
    monkeypatch.setattr(pipeline, "sample_frames", lambda path, fps: [(1, None)])

    class Detector:
        model_id = "mock:v1"
        calls = 0

        def detect(self, frames):
            self.calls += 1
            return [FrameScore(t, "nudity", 0.9, ["exposed"]) for t, _ in frames]

    def dense(path, detector, scores, review, duration, fps):
        return scores

    monkeypatch.setattr(pipeline, "refine", dense)
    detector = Detector()
    settings = {"snap_window": 0}
    first = pipeline.analyze_visual(path, 3, settings, detectors={"nudity": detector})
    assert len(first) == 1
    assert pipeline.analyze_visual(path, 3, settings, detectors={"nudity": detector}) == first
    assert detector.calls == 1
    settings["nudity_threshold"] = 0.95
    assert not pipeline.analyze_visual(path, 3, settings, detectors={"nudity": detector})
    assert detector.calls == 1  # Policy changes reuse raw per-frame scores.
    settings["sample_fps"] = 4
    pipeline.analyze_visual(path, 3, settings, detectors={"nudity": detector})
    assert detector.calls == 2
    path.write_bytes(b"different media")
    pipeline.analyze_visual(path, 3, settings, detectors={"nudity": detector})
    assert detector.calls == 3


def test_shot_detector_mock(monkeypatch):
    from angel_editor.visual.shots import detect_shots

    class Cut:
        def __init__(self, t):
            self.t = t

        def get_seconds(self):
            return self.t

    monkeypatch.setitem(
        sys.modules,
        "scenedetect",
        types.SimpleNamespace(
            ContentDetector=lambda: "content",
            detect=lambda path, detector: [(Cut(0), Cut(1)), (Cut(1), Cut(3))],
        ),
    )
    assert detect_shots("file") == [0, 1, 3]
