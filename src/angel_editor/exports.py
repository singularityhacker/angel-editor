import json
from dataclasses import asdict


def kodi_edl(spans):
    return "".join(f"{a / 1e6:.3f} {b / 1e6:.3f} 1\n" for a, b in spans)


def mplayer_edl(spans):
    return "".join(f"{a / 1e6:.3f} {b / 1e6:.3f} 1\n" for a, b in spans)


def timeline(identity, settings, events):
    return (
        json.dumps(
            {
                "schema_version": 1,
                "source_fingerprint": identity,
                "settings": settings,
                "events": [asdict(e) for e in events],
            },
            indent=2,
        )
        + "\n"
    )
