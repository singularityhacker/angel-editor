import json
from dataclasses import asdict


def kodi_edl(spans, skips=()):
    return "".join(
        f"{a / 1e6:.3f} {b / 1e6:.3f} {action}\n"
        for a, b, action in sorted([(a, b, 1) for a, b in spans] + [(a, b, 0) for a, b in skips])
    )


def mplayer_edl(spans, skips=()):
    return "".join(
        f"{a / 1e6:.3f} {b / 1e6:.3f} {action}\n"
        for a, b, action in sorted([(a, b, 1) for a, b in spans] + [(a, b, 0) for a, b in skips])
    )


def timeline(identity, settings, events):
    return (
        json.dumps(
            {
                "schema_version": 2,
                "source_fingerprint": identity,
                "settings": settings,
                "events": [asdict(e) for e in events],
            },
            indent=2,
        )
        + "\n"
    )
