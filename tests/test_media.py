import array
import hashlib
import json
import math
import shutil
import subprocess

import pytest

from angel_editor.cli import main
from angel_editor.media import probe, render, run
from angel_editor.pipeline import analyze
from angel_editor.schema import Word

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")


@pytest.fixture(params=[2, 6])
def media(tmp_path, request):
    path = tmp_path / "sample.mp4"
    layout = "stereo" if request.param == 2 else "5.1"
    expressions = "|".join(["0.15*sin(2*PI*80*t)"] * request.param)
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x64:rate=25",
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc={expressions}:s=48000:c={layout}",
            "-t",
            "2",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ]
    )
    return path, request.param


def decode(path, channels):
    data = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-",
        ]
    )
    samples = array.array("f")
    samples.frombytes(data)
    return [samples[c::channels] for c in range(channels)]


def rms(samples):
    return math.sqrt(sum(s * s for s in samples) / len(samples))


def video_hash(path):
    return hashlib.sha256(
        subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-c",
                "copy",
                "-f",
                "data",
                "-",
            ]
        )
    ).hexdigest()


@pytest.mark.parametrize("mode", ["mute", "bleep"])
def test_render(media, mode):
    path, channels = media
    output = path.with_name("out.mp4")
    info = probe(path)
    render(path, output, info, [(500000, 1300000)], mode)
    assert video_hash(path) == video_hash(output)
    assert abs(float(probe(output)["format"]["duration"]) - 2) < 0.05
    for channel, samples in enumerate(decode(output, channels)):
        window = samples[round(0.7 * 48000) : round(1.1 * 48000)]
        assert rms(samples[5000:15000]) > 0.03
        if mode == "mute" or (channels == 6 and channel == 3):
            assert rms(window) < 0.001
        else:

            def energy(frequency, window=window):
                return abs(
                    sum(
                        s
                        * complex(
                            math.cos(2 * math.pi * frequency * i / 48000),
                            math.sin(2 * math.pi * frequency * i / 48000),
                        )
                        for i, s in enumerate(window)
                    )
                )

            assert energy(1000) > 20 * energy(80)
    with pytest.raises(FileExistsError):
        render(path, output, info, [])
    with pytest.raises(ValueError):
        render(path, path, info, [], overwrite=True)


def settings(**overrides):
    return dict(
        subs="auto",
        asr="off",
        model="small",
        language="en",
        no_cache=False,
        strictness="moderate",
        mode="mute",
        **overrides,
    )


def test_subs_cli_batch(media, capsys):
    path, _ = media
    path.with_suffix(".srt").write_text("1\n00:00:00,500 --> 00:00:01,000\nOh shit!\n")
    identity, events, warnings = analyze(path, probe(path), settings())
    assert identity and events[0].accuracy == "cue" and warnings
    assert events[0].start_us == 500000
    assert main(["scan", str(path), "--asr", "off"]) == 0
    assert path.with_name("sample.angel.json").exists()
    assert main(["clean", str(path), "--asr", "off", "--json", "--edl", "kodi", "--overwrite"]) == 0
    data = json.loads(path.with_name("sample.angel.json").read_text())
    assert data["events"][0]["source"] == "subs"
    assert main(["clean", str(path), "--asr", "off"]) == 1
    (path.parent / "broken.mp4").write_text("broken")
    assert main(["clean", str(path.parent), "--asr", "off", "--overwrite"]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_mock_asr_cache(media, tmp_path, monkeypatch):
    path, _ = media
    monkeypatch.setenv("ANGEL_CACHE_DIR", str(tmp_path / "cache"))

    class Backend:
        calls = 0

        def transcribe(self, audio, **kwargs):
            self.calls += 1
            assert kwargs == {"model": "small", "language": "en"}
            return [Word(100000, 200000, "shit")]

    backend = Backend()
    config = settings()
    config.update(subs="off", asr="auto")
    first = analyze(path, probe(path), config, transcriber=backend)
    assert first[1][0].source == "asr"
    assert analyze(path, probe(path), config, transcriber=backend) == first
    assert backend.calls == 1
    path.with_suffix(".vtt").write_text("WEBVTT\n\n00:00.500 --> 00:01.000\nshit\n")
    config["subs"] = "auto"
    assert analyze(path, probe(path), config, transcriber=backend)[1][0].accuracy == "word"
    assert backend.calls == 2


def test_dry_no_changes(media):
    path, _ = media
    path.with_suffix(".srt").write_text("1\n00:00:00,500 --> 00:00:01,000\nhello\n")
    assert main(["clean", str(path), "--asr", "off", "--dry-run"]) == 0
    assert not path.with_name("sample.angel.mp4").exists()
    assert main(["clean", str(path), "--asr", "off"]) == 0
    assert video_hash(path) == video_hash(path.with_name("sample.angel.mp4"))


def test_embedded_and_multiple_tracks(media):
    path, channels = media
    subs = path.with_suffix(".srt")
    subs.write_text("1\n00:00:00,500 --> 00:00:01,000\nshit\n")
    embedded = path.with_name("embedded.mkv")
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-i",
            str(subs),
            "-map",
            "0:v",
            "-map",
            "0:a",
            "-map",
            "0:a",
            "-map",
            "1:0",
            "-c",
            "copy",
            "-metadata:s:a:1",
            "language=eng",
            str(embedded),
        ]
    )
    subs.unlink()
    info = probe(embedded)
    _, events, _ = analyze(embedded, info, settings())
    assert events[0].accuracy == "cue"
    output = path.with_name("multi.mp4")
    render(embedded, output, info, [(400000, 1400000)])
    output_info = probe(output)
    audio = [s for s in output_info["streams"] if s["codec_type"] == "audio"]
    assert len(audio) == 2 and audio[1]["tags"]["language"] == "eng"
    assert (
        next(s for s in output_info["streams"] if s["codec_type"] == "subtitle")["codec_name"]
        == "mov_text"
    )
    for track in range(2):
        data = subprocess.check_output(
            ["ffmpeg", "-v", "error", "-i", str(output), "-map", f"0:a:{track}", "-f", "f32le", "-"]
        )
        samples = array.array("f")
        samples.frombytes(data)
        for channel in range(channels):
            assert rms(samples[channel::channels][35000:50000]) < 0.001


def test_cut_render(media):
    from angel_editor.media import render_cuts

    path, channels = media
    output = path.with_name("cut.mp4")
    render_cuts(
        path,
        output,
        probe(path),
        [(1400000, 1800000)],
        [(200000, 500000), (800000, 1100000)],
        preset="ultrafast",
    )
    info = probe(output)
    assert abs(float(info["format"]["duration"]) - 1.4) < 0.06
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    video, audio = (
        next(s for s in info["streams"] if s["codec_type"] == kind) for kind in ("video", "audio")
    )
    assert abs(float(video["duration"]) - float(audio["duration"])) < 0.05
    for samples in decode(output, channels):
        assert rms(samples[round(0.9 * 48000) : round(1.1 * 48000)]) < 0.001


def test_sampler_timestamps(media, monkeypatch):
    import sys
    import types

    from angel_editor.visual.sampler import sample_frames

    # Core CI omits numpy/visual extras; retain real ffmpeg decoding and timestamps.
    monkeypatch.setitem(
        sys.modules,
        "numpy",
        types.SimpleNamespace(
            uint8="uint8",
            frombuffer=lambda data, dtype: types.SimpleNamespace(
                reshape=lambda *shape: types.SimpleNamespace(shape=shape, data=data)
            ),
        ),
    )
    path, _ = media
    frames = list(sample_frames(path, 2))
    assert [t for t, _ in frames] == [0, 0.5, 1, 1.5]
    dense = list(sample_frames(path, 8, 0.5, 1.5))
    assert [t for t, _ in dense] == [0.5 + i / 8 for i in range(8)]
    fractional = list(sample_frames(path, 8, 0.55, 1.43))
    assert [t for t, _ in fractional] == [0.625 + i / 8 for i in range(7)]


def test_sampler_streams_and_closes(media, monkeypatch, tmp_path):
    import subprocess
    import sys
    import tempfile
    import types

    from angel_editor.visual import sampler

    monkeypatch.setitem(
        sys.modules,
        "numpy",
        types.SimpleNamespace(
            uint8="uint8",
            frombuffer=lambda data, dtype: types.SimpleNamespace(
                reshape=lambda *shape: types.SimpleNamespace(shape=shape, data=data)
            ),
        ),
    )
    processes = []
    popen = subprocess.Popen

    def paced_decoder(args, **kwargs):
        if args[0] == "ffprobe":
            return popen(args, **kwargs)
        assert args[-1] == "pipe:1" and "rawvideo" in args
        args.insert(args.index("-i"), "-re")
        process = popen(args, **kwargs)
        processes.append(process)
        return process

    def no_temporary_files(*args, **kwargs):
        pytest.fail("Sampler must not create temporary frame files")

    monkeypatch.setattr(sampler.subprocess, "Popen", paced_decoder)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", no_temporary_files)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", no_temporary_files)
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    frames = sampler.sample_frames(media[0], 8)
    try:
        t, frame = next(frames)
        assert t == 0
        assert max(frame.shape[:2]) <= 640
        assert len(frame.data) == frame.shape[0] * frame.shape[1] * 3
        assert processes[0].poll() is None  # First yield precedes decoder completion.
        assert set(tmp_path.iterdir()) == before
    finally:
        frames.close()
    assert processes[0].poll() is not None
    assert processes[0].stdout.closed and processes[0].stderr.closed


def test_mock_visual_cli(media, monkeypatch):
    from angel_editor.visual import pipeline
    from angel_editor.visual.detectors import FrameScore

    path, _ = media

    class Detector:
        model_id = "mock-visual"

        def detect(self, frames):
            return [FrameScore(0.5, "nudity", 0.95, ["exposed"])]

    monkeypatch.setattr(pipeline, "available", lambda: True)
    monkeypatch.setattr("angel_editor.cli.available", lambda: True)
    monkeypatch.setattr(pipeline, "NudityDetector", Detector)
    monkeypatch.setattr(pipeline, "ViolenceDetector", lambda model: Detector())
    monkeypatch.setattr(pipeline, "detect_shots", lambda path: [])
    monkeypatch.setattr(pipeline, "sample_frames", lambda path, fps: [])
    monkeypatch.setattr(pipeline, "refine", lambda path, detector, scores, *args: scores)
    assert (
        main(
            [
                "run",
                str(path),
                "--subs",
                "off",
                "--asr",
                "off",
                "--json",
                "--edl",
                "kodi",
                "--no-cache",
                "--snap-window",
                "0",
            ]
        )
        == 0
    )
    output = path.with_name("sample.angel.mp4")
    assert float(probe(output)["format"]["duration"]) < 1.5
    data = json.loads(output.with_suffix(".json").read_text())
    assert data["events"][0]["source"] == "mock-visual"
    assert output.with_suffix(".edl").read_text().strip().endswith(" 0")


def test_sampler_timestamps_with_container_offset(tmp_path, monkeypatch):
    import sys
    import types

    from angel_editor.visual.sampler import sample_frames

    monkeypatch.setitem(
        sys.modules,
        "numpy",
        types.SimpleNamespace(
            uint8="uint8",
            frombuffer=lambda data, dtype: types.SimpleNamespace(
                reshape=lambda *shape: types.SimpleNamespace(shape=shape, data=data)
            ),
        ),
    )
    path = tmp_path / "offset.mp4"
    run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=25", "-t", "3"]
        + ["-c:v", "mpeg4", "-output_ts_offset", "1.4", str(path)]
    )
    # Timestamps are zero-based media time even though the container starts at 1.4 s.
    coarse = [t for t, _ in sample_frames(path, 2)]
    assert 0 <= coarse[0] < 0.5 and 2.5 <= coarse[-1] < 3
    dense = [t for t, _ in sample_frames(path, 8, 1, 2)]
    assert len(dense) >= 7 and all(1 <= t < 2 for t in dense)
