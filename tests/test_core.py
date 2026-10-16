import json

import pytest

from angel_editor import cache
from angel_editor.cli import main
from angel_editor.exports import kodi_edl, mplayer_edl, timeline
from angel_editor.matching import match, tokens
from angel_editor.schema import Event, Word, intervals
from angel_editor.subtitles import parse


def test_matching():
    assert tokens("ＦＵＣＫ! Don’t") == ["fuck", "don't"]
    words = [
        Word(i * 100000, (i + 1) * 100000, text)
        for i, text in enumerate(["Scunthorpe", "assassin", "cocktail", "damn", "shit", "fucking"])
    ]
    assert [e.severity for e in match(words, "strict")] == [1, 2, 3]
    assert [e.severity for e in match(words)] == [2, 3]
    assert [e.severity for e in match(words, "mild")] == [3]
    assert match([Word(0, 100, "son of a bitch")])[0].term == "son of a bitch"
    assert not match(words, profile={"allowlist": ["shit", "fucking"]})
    assert not match(
        words,
        profile={"profanity": {"min_severity": 3}, "bodily": {"min_severity": 3}},
        strictness="strict",
    )[:-1]
    assert match(
        [Word(0, 1, "custom")],
        profile={"extra_words": [{"term": "custom", "category": "profanity", "severity": 2}]},
    )


def event(a, b):
    return Event(a, b, "shit", "shit", 2, "bodily", "asr", 0.9)


def test_intervals_exports():
    events = [event(0, 200000), event(480000, 600000), event(950000, 1100000)]
    spans = intervals(events, 1000000)
    assert spans == [(0, 750000), (850000, 1000000)]
    expected = "0.000 0.750 1\n0.850 1.000 1\n"
    assert kodi_edl(spans) == mplayer_edl(spans) == expected
    data = json.loads(timeline("abc", {"mode": "mute"}, events))
    assert data["source_fingerprint"] == "abc"
    assert set(data["events"][0]) == {
        "start_us",
        "end_us",
        "word",
        "term",
        "severity",
        "category",
        "source",
        "confidence",
        "action",
        "accuracy",
    }


@pytest.mark.parametrize("header,stamp", [("", "00:00:01,000"), ("WEBVTT\n\n", "00:01.000")])
def test_subtitles(header, stamp):
    cue = parse(header + "1\n" + stamp + " --> 00:00:02.000 align:start\n<i>Oh shit!</i>\n")[0]
    assert (cue.start_us, cue.end_us, cue.word) == (1000000, 2000000, "Oh shit!")


def test_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGEL_CACHE_DIR", str(tmp_path / "cache"))
    calls = []

    def produce():
        calls.append(1)
        return [Word(0, 1, "hello")]

    assert cache.transcript("key", produce) == cache.transcript("key", produce)
    assert len(calls) == 1
    cache.transcript("key", produce, False)
    assert len(calls) == 2
    path = tmp_path / "file"
    path.write_text("first")
    first = cache.fingerprint(path)
    path.write_text("other")
    assert cache.fingerprint(path) != first


def test_missing_tools(monkeypatch, capsys):
    monkeypatch.setenv("PATH", "")
    assert main(["doctor"]) == 2
    assert "FAIL ffmpeg" in capsys.readouterr().out
    assert main(["clean", "missing.mp4"]) == 2


def test_help():
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
