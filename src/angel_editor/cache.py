import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from .schema import Word


def directory():
    return Path(os.environ.get("ANGEL_CACHE_DIR", Path.home() / ".cache/angel-editor"))


def fingerprint(path):
    stat = path.stat()
    digest = hashlib.sha256(f"{stat.st_size}:{stat.st_mtime_ns}".encode())
    with path.open("rb") as source:
        digest.update(source.read(1024 * 1024))
        source.seek(max(0, stat.st_size - 1024 * 1024))
        digest.update(source.read())
    return digest.hexdigest()


def transcript(key, produce, enabled=True):
    path = directory() / (hashlib.sha256(key.encode()).hexdigest() + ".json")
    if enabled and path.exists():
        try:
            return [Word(**w) for w in json.loads(path.read_text())]
        except (ValueError, TypeError):
            pass
    words = produce()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as target:
            json.dump([asdict(w) for w in words], target)
        Path(target.name).replace(path)
    return words
