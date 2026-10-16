import json
import subprocess
import tempfile
from pathlib import Path


def run(args):
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-3000:])
    return result.stdout


def probe(path):
    return json.loads(
        run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    )


def extract_audio(path, output, start=None, end=None, track=0):
    args = ["ffmpeg", "-v", "error", "-y", "-i", str(path)]
    if start is not None:
        args += ["-ss", str(start / 1e6), "-t", str((end - start) / 1e6)]
    run(args + ["-map", f"0:a:{track}", "-ac", "1", "-ar", "16000", str(output)])


def render(path, output, info, spans, mode="mute", level=-18, overwrite=False):
    path, output = Path(path), Path(output)
    if path.resolve() == output.resolve():
        raise ValueError("Output must differ from input")
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output}; use --overwrite")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    # Write beside the destination and publish only after ffmpeg succeeds.
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        temporary = Path(directory) / "output.mp4"
        args = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)]
        graph = []
        gate = "+".join(f"gte(t,{a / 1e6:.6f})*lt(t,{b / 1e6:.6f})" for a, b in spans)
        for i, stream in enumerate(audio):
            if not spans:
                break
            graph.append(f"[0:a:{i}]volume=0:enable='{gate}'[muted{i}]")
            if mode == "bleep":
                layout = stream.get("channel_layout") or {1: "mono", 2: "stereo", 6: "5.1"}.get(
                    stream["channels"]
                )
                if not layout:
                    raise ValueError("Unsupported channel layout for bleep")
                expression = f"{10 ** (level / 20):.8f}*sin(2*PI*1000*t)*({gate})"
                expressions = "|".join([expression] * stream["channels"])
                duration = float(info["format"]["duration"])
                graph.append(f"aevalsrc='{expressions}':s=48000:d={duration}:c={layout}[tone{i}]")
                graph.append(f"[muted{i}][tone{i}]amix=inputs=2:normalize=0:duration=first[out{i}]")
            else:
                graph.append(f"[muted{i}]anull[out{i}]")
        if graph:
            script = Path(directory) / "filters.txt"
            script.write_text(";\n".join(graph))
            args += ["-filter_complex_script", str(script)]
        args += ["-map", "0"]
        if graph:
            args += ["-map", "-0:a"]
            for i in range(len(audio)):
                args += ["-map", f"[out{i}]"]
        args += ["-c", "copy"]
        if graph:
            args += ["-c:a", "aac"]
            for i, stream in enumerate(audio):
                bitrate = max(192000, int(stream.get("bit_rate", 0)), 96000 * stream["channels"])
                args += [f"-b:a:{i}", str(bitrate)]
                for key, value in stream.get("tags", {}).items():
                    args += [f"-metadata:s:a:{i}", f"{key}={value}"]
                dispositions = "+".join(k for k, v in stream.get("disposition", {}).items() if v)
                args += [f"-disposition:a:{i}", dispositions or "0"]
        for i, stream in enumerate(s for s in info["streams"] if s["codec_type"] == "subtitle"):
            if stream["codec_name"] in {"subrip", "ass", "ssa", "webvtt", "mov_text", "text"}:
                args += [f"-c:s:{i}", "mov_text"]
            else:
                raise ValueError("Bitmap subtitles cannot be retained in MP4")
        run(args + ["-movflags", "+faststart", str(temporary)])
        temporary.replace(output)
