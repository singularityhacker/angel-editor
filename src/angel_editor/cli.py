import argparse
import shutil
import sys
from pathlib import Path

from . import cache
from .exports import kodi_edl, mplayer_edl, timeline
from .matching import tomllib
from .media import probe, render, run
from .pipeline import analyze
from .schema import intervals

EXTENSIONS = {".mp4", ".m4v", ".mkv", ".mov"}


def doctor():
    failed = False
    for binary in ("ffmpeg", "ffprobe"):
        if shutil.which(binary):
            print(f"PASS {run([binary, '-version']).splitlines()[0]}")
        else:
            print(f"FAIL {binary} missing from PATH")
            failed = True
    try:
        import importlib

        importlib.import_module("faster_whisper")
        speech = True
    except (ImportError, OSError):
        speech = False
    print(
        f"{'PASS' if speech else 'WARN'} faster-whisper {'available' if speech else 'not installed'}"
    )
    print("WARN Models download on first ASR use; pre-cache the selected model for offline use")
    print("PASS CPU int8 backend; CUDA requires a compatible faster-whisper/CUDA installation")
    try:
        import tempfile

        cache.directory().mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=cache.directory()):
            pass
        print(f"PASS cache writable: {cache.directory()}")
    except OSError as error:
        print(f"FAIL cache: {error}")
        failed = True
    return 2 if failed else 0


def parser():
    root = argparse.ArgumentParser(
        prog="angel", description="Local language filtering to clean MP4"
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check local dependencies")
    for name in ("clean", "scan"):
        command = commands.add_parser(name)
        command.add_argument("inputs", nargs="+")
        command.add_argument("-o", "--output")
        command.add_argument("--mode", choices=["mute", "bleep"], default="mute")
        command.add_argument(
            "--strictness", choices=["mild", "moderate", "strict"], default="moderate"
        )
        command.add_argument("--subs", default="auto", metavar="auto|PATH|off")
        command.add_argument("--asr", choices=["auto", "off"], default="auto")
        command.add_argument("--model", default="small")
        command.add_argument("--language", default="en")
        command.add_argument("--pad-before", type=int, default=100, help="Milliseconds")
        command.add_argument("--pad-after", type=int, default=150, help="Milliseconds")
        command.add_argument("--bleep-level", type=float, default=-18, help="Tone level in dBFS")
        command.add_argument("--profile", type=Path)
        command.add_argument("--edl", choices=["kodi", "mplayer"])
        for flag in ("json", "dry-run", "no-cache", "recursive", "overwrite"):
            command.add_argument("--" + flag, action="store_true")
    return root


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if any(not shutil.which(binary) for binary in ("ffmpeg", "ffprobe")):
        print("Setup error: ffmpeg and ffprobe are required; run angel doctor", file=sys.stderr)
        return 2
    if args.pad_before < 0 or args.pad_after < 0:
        root.error("Padding must be nonnegative")
    settings = {
        key: value
        for key, value in vars(args).items()
        if key not in {"inputs", "profile", "output", "command"}
    }
    try:
        profile = tomllib.loads(args.profile.read_text()) if args.profile else {}
        if not isinstance(profile.get("allowlist", []), list) or not all(
            isinstance(word, str) for word in profile.get("allowlist", [])
        ):
            raise ValueError("Profile allowlist must be an array of strings")
        for entry in profile.get("extra_words", []):
            if not isinstance(entry, dict) or not isinstance(entry.get("term"), str):
                raise TypeError("Profile extra_words must contain term tables")
            if entry.get("severity") not in (1, 2, 3) or entry.get("category") not in {
                "profanity",
                "sexual",
                "slur",
                "blasphemy",
                "bodily",
            }:
                raise ValueError("Extra words require a valid category and severity 1–3")
        for category in ("profanity", "sexual", "slur", "blasphemy", "bodily"):
            if category in profile and not isinstance(profile[category], dict):
                raise ValueError("Profile categories must be tables")
            if category in profile and profile[category].get("min_severity", 2) not in (1, 2, 3):
                raise ValueError("Profile min_severity must be 1, 2, or 3")
    except (OSError, ValueError, TypeError) as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 2
    settings["profile"] = profile
    paths = []
    batch = any(Path(p).is_dir() for p in args.inputs) or len(args.inputs) > 1
    for value in args.inputs:
        path = Path(value)
        if path.is_dir():
            paths.extend(
                sorted(
                    p
                    for p in (path.rglob("*") if args.recursive else path.iterdir())
                    if p.suffix.lower() in EXTENSIONS and ".angel." not in p.name
                )
            )
        else:
            paths.append(path)
    paths = list(dict.fromkeys(paths))
    if not paths:
        root.error("No video files found")
    output_dir = Path(args.output) if args.output else None
    if batch and output_dir and not output_dir.is_dir():
        root.error("Batch -o must be an existing directory")
    failures = 0
    for path in paths:
        try:
            output = (
                output_dir / f"{path.stem}.angel.mp4"
                if output_dir and output_dir.is_dir()
                else output_dir or path.with_name(f"{path.stem}.angel.mp4")
            )
            if output.resolve() == path.resolve():
                raise ValueError("Output must differ from input")
            info = probe(path)
            identity, events, warnings = analyze(path, info, settings, profile)
            spans = intervals(
                events,
                round(float(info["format"]["duration"]) * 1e6),
                args.pad_before * 1000,
                args.pad_after * 1000,
            )
            for warning in warnings:
                print(f"WARN {path.name}: {warning}", file=sys.stderr)
            if args.command == "scan":
                print(timeline(identity, settings, events), end="")
                continue
            exports = {}
            if args.json:
                exports[output.with_suffix(".json")] = timeline(identity, settings, events)
            if args.edl:
                writer = kodi_edl if args.edl == "kodi" else mplayer_edl
                exports[output.with_suffix(".edl")] = writer(spans)
            for target in [output, *exports]:
                if target.exists() and not args.overwrite and not args.dry_run:
                    raise FileExistsError(f"Output exists: {target}; use --overwrite")
                if target.resolve() in {p.resolve() for p in paths}:
                    raise ValueError("Output would overwrite an input")
            if not args.dry_run:
                render(path, output, info, spans, args.mode, args.bleep_level, args.overwrite)
                for target, content in exports.items():
                    target.write_text(content)
            print(
                f"{path.name}: {len(events)} events; "
                f"{'dry run' if args.dry_run else output}"
                f"{' (no changes)' if not events else ''}"
            )
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
            failures += 1
            print(f"FAIL {path}: {error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
