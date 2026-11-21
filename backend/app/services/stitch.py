# SPDX-License-Identifier: AGPL-3.0-or-later
"""Join several MP4 clips into one with ffmpeg (multi-scene video).

No shell is ever involved: every command is an argument list, the clip paths come from our own
asset store (server-chosen hex names) and the output goes to a fresh temp file. ffmpeg runs as an
async subprocess with a hard timeout and is killed on timeout. Its output is logged (not shown to
users) and never leaves this module: callers only see ``StitchError`` with a safe code.

Strategy: the concat demuxer with ``-c copy`` when every clip has the same codec, size, frame
rate and audio layout (fast, lossless). Otherwise, or if that fails, a re-encode through the
concat filter (libx264, yuv420p, +faststart, AAC only when every clip has audio).
"""

import asyncio
import contextlib
import json
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

log = logging.getLogger("aurevid.stitch")

FALLBACK_FPS = "24"


class StitchError(Exception):
    """Joining failed. ``code`` is safe to show (an i18n error code); details only go to logs."""

    def __init__(self, code: str = "stitch_failed") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ClipInfo:
    codec: str
    width: int
    height: int
    pix_fmt: str
    fps: str  # "24/1"
    has_audio: bool
    audio_codec: str = ""
    duration: float = 0.0

    def layout(self) -> tuple:
        """What must match for ``-c copy`` to be safe."""
        return (self.codec, self.width, self.height, self.pix_fmt, self.fps, self.audio_codec)


def ffmpeg_bin() -> str | None:
    return shutil.which(get_settings().ffmpeg_path)


def ffprobe_bin() -> str | None:
    configured = get_settings().ffmpeg_path
    sibling = Path(configured).with_name("ffprobe") if "/" in configured else None
    if sibling is not None and sibling.exists():
        return str(sibling)
    return shutil.which("ffprobe")


def available() -> bool:
    return ffmpeg_bin() is not None and ffprobe_bin() is not None


def parse_probe(raw: str) -> ClipInfo:
    """Read ``ffprobe -print_format json -show_streams -show_format`` output."""
    data = json.loads(raw)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise StitchError()
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float(data.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return ClipInfo(
        codec=str(video.get("codec_name", "")),
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        pix_fmt=str(video.get("pix_fmt", "")),
        fps=str(video.get("avg_frame_rate") or video.get("r_frame_rate") or ""),
        has_audio=audio is not None,
        audio_codec=str(audio.get("codec_name", "")) if audio else "",
        duration=duration,
    )


def can_copy(clips: list[ClipInfo]) -> bool:
    """``-c copy`` is only safe when every clip shares one layout (and all have audio or none)."""
    return len({c.layout() for c in clips}) == 1 and clips[0].width > 0


def _escape_concat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def concat_list(paths: list[Path]) -> str:
    return "".join(f"file '{_escape_concat_path(p)}'\n" for p in paths)


_COMMON = ["-nostdin", "-hide_banner", "-loglevel", "error", "-y"]


def copy_command(ffmpeg: str, list_file: Path, out: Path) -> list[str]:
    return [
        ffmpeg, *_COMMON,
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", "-movflags", "+faststart",
        str(out),
    ]  # fmt: skip


def reencode_command(ffmpeg: str, paths: list[Path], clips: list[ClipInfo], out: Path) -> list[str]:
    """Concat *filter* (scales every clip to the first one's size), so different sizes, frame
    rates or codecs still join. Audio is kept only when every clip has it."""
    first = clips[0]
    width, height = first.width - first.width % 2, first.height - first.height % 2
    fps = first.fps if first.fps and not first.fps.startswith("0") else FALLBACK_FPS
    with_audio = all(c.has_audio for c in clips)
    cmd = [ffmpeg, *_COMMON]
    for p in paths:
        cmd += ["-i", str(p)]
    parts, joined = [], ""
    for i in range(len(paths)):
        parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v{i}]"
        )
        joined += f"[v{i}]"
        if with_audio:
            parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
            joined += f"[a{i}]"
    parts.append(
        f"{joined}concat=n={len(paths)}:v=1:a={1 if with_audio else 0}[v]"
        + ("[a]" if with_audio else "")
    )
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]"]
    if with_audio:
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20"]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


async def _run(cmd: list[str], limit_s: float) -> tuple[int, bytes]:
    """Run without a shell. Kills the process and raises StitchError on timeout."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=limit_s)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        await proc.wait()
        log.error("ffmpeg timed out after %ss", limit_s)
        raise StitchError() from None
    return proc.returncode or 0, stdout if proc.returncode == 0 else stderr


async def probe(path: Path) -> ClipInfo:
    ffprobe = ffprobe_bin()
    if ffprobe is None:
        raise StitchError()
    cmd = [
        ffprobe, "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ]  # fmt: skip
    code, out = await _run(cmd, 30)
    if code != 0:
        log.error("ffprobe failed: %s", out[-300:].decode(errors="replace"))
        raise StitchError()
    try:
        return parse_probe(out.decode())
    except (ValueError, KeyError):
        raise StitchError() from None


async def concat_clips(paths: list[Path], out: Path) -> ClipInfo:
    """Join ``paths`` (in order) into ``out`` and return the probed result."""
    if len(paths) < 2:
        raise StitchError()
    ffmpeg = ffmpeg_bin()
    if ffmpeg is None or ffprobe_bin() is None:
        log.error("ffmpeg is not installed")
        raise StitchError()
    timeout = get_settings().stitch_timeout_seconds
    clips = [await probe(p) for p in paths]

    done = False
    if can_copy(clips):
        with tempfile.TemporaryDirectory(prefix="stitch-", dir=out.parent) as tmp:
            list_file = Path(tmp) / "clips.txt"
            list_file.write_text(concat_list(paths), encoding="utf-8")
            code, err = await _run(copy_command(ffmpeg, list_file, out), timeout)
        done = code == 0
        if not done:
            log.warning("ffmpeg copy failed, re-encoding: %s", err[-300:].decode(errors="replace"))
    if not done:
        code, err = await _run(reencode_command(ffmpeg, paths, clips, out), timeout)
        if code != 0:
            log.error("ffmpeg re-encode failed: %s", err[-500:].decode(errors="replace"))
            raise StitchError()
    return await probe(out)
