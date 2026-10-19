import re
import unicodedata
from importlib.resources import files

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .schema import Event


def tokens(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", text)


def lexicon():
    return tomllib.loads(files("angel_editor").joinpath("data/lexicon_en.toml").read_text())


def match(words, strictness="moderate", profile=None, source="asr", mode="mute"):
    profile = profile or {}
    data = lexicon()
    entries = data["entries"] + profile.get("extra_words", [])
    allow = {tuple(tokens(s)) for s in data["exceptions"] + profile.get("allowlist", [])}
    flattened = [(token, w) for w in words for token in tokens(w.word)]
    result = []
    for entry in entries:
        minimum = profile.get(entry["category"], {}).get(
            "min_severity", {"strict": 1, "moderate": 2, "mild": 3, "lenient": 3}[strictness]
        )
        if entry["severity"] < minimum:
            continue
        for variant in [entry["term"], *entry.get("variants", [])]:
            target = tuple(tokens(variant))
            if not target or target in allow:
                continue
            for i in range(len(flattened) - len(target) + 1):
                part = flattened[i : i + len(target)]
                if tuple(t for t, _ in part) != target:
                    continue
                if any(tuple(tokens(w.word)) in allow for _, w in part):
                    continue
                first, last = part[0][1], part[-1][1]
                event = Event(
                    first.start_us,
                    last.end_us,
                    " ".join(t for t, _ in part),
                    entry["term"],
                    entry["severity"],
                    entry["category"],
                    source,
                    min(w.confidence for _, w in part),
                    mode,
                )
                if event not in result:
                    result.append(event)
    return sorted(result, key=lambda e: (e.start_us, e.end_us, e.term))
