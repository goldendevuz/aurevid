# SPDX-License-Identifier: AGPL-3.0-or-later
"""Media validation by content, re-encoding, previews and safe storage.

Images: verified by Pillow, allowlisted formats, pixel cap, re-encoded to WebP (drops metadata
and embedded payloads). Large images also get a small preview so galleries stay fast.
Videos: only from providers (never user uploads); the MP4 container structure is checked strictly.
"""

import io
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from app.config import get_settings

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
PREVIEW_MAX_SIDE = 1024


class InvalidImageError(ValueError):
    pass


@dataclass
class StoredImage:
    storage_key: str
    mime: str
    width: int
    height: int
    size_bytes: int
    preview_key: str | None = None


def asset_root() -> Path:
    root = Path(get_settings().asset_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def tmp_dir() -> Path:
    """Scratch space next to the assets (same filesystem, so finished files can be renamed in)."""
    path = asset_root().parent / "_tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_path(storage_key: str) -> Path:
    """Map a server-generated key to a path, refusing anything that escapes the asset root."""
    if not storage_key or "/" in storage_key or "\\" in storage_key or storage_key.startswith("."):
        raise InvalidImageError("bad storage key")
    root = asset_root()
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise InvalidImageError("bad storage key")
    return path


# --- images ----------------------------------------------------------------------------------


def decode_image(data: bytes, max_bytes: int | None = None) -> Image.Image:
    """Validate bytes as an allowed image (by content) and return a clean RGB/RGBA copy."""
    s = get_settings()
    if not data:
        raise InvalidImageError("empty file")
    if len(data) > (max_bytes or s.max_upload_bytes):
        raise InvalidImageError("file too large")
    Image.MAX_IMAGE_PIXELS = s.max_image_pixels
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise InvalidImageError("unsupported image type")
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.width * img.height > s.max_image_pixels:
                raise InvalidImageError("image too large")
            mode = "RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB"
            return img.convert(mode)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise InvalidImageError("not a valid image") from exc


def _webp(img: Image.Image, quality: int = 90) -> bytes:
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=quality, method=4)
    return out.getvalue()


def reencode_image(data: bytes) -> tuple[bytes, int, int]:
    img = decode_image(data)
    return _webp(img), img.width, img.height


def save_image(img: Image.Image) -> StoredImage:
    """Encode a validated image to WebP (plus a preview when it is large) and store it."""
    if img.width * img.height > get_settings().max_image_pixels:
        raise InvalidImageError("image too large")
    full = _webp(img, quality=92)
    key = f"{secrets.token_hex(16)}.webp"
    asset_path(key).write_bytes(full)
    preview_key = None
    if max(img.size) > PREVIEW_MAX_SIDE:
        small = img.copy()
        small.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE), Image.Resampling.LANCZOS)
        preview_key = key.replace(".webp", ".p.webp")
        asset_path(preview_key).write_bytes(_webp(small, quality=85))
    return StoredImage(key, "image/webp", img.width, img.height, len(full), preview_key)


def store_image(data: bytes, max_bytes: int | None = None) -> StoredImage:
    return save_image(decode_image(data, max_bytes))


def load_stored_image(storage_key: str) -> Image.Image:
    s = get_settings()
    Image.MAX_IMAGE_PIXELS = s.max_image_pixels
    with Image.open(asset_path(storage_key)) as img:
        img.load()
        return img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")


def image_for_provider(storage_key: str, max_side: int = 1280) -> bytes:
    """Load one of our stored images as a compact JPEG start frame for image-to-video."""
    frame = load_stored_image(storage_key).convert("RGB")
    frame.thumbnail((max_side, max_side))
    out = io.BytesIO()
    frame.save(out, format="JPEG", quality=90)
    return out.getvalue()


def delete_stored(storage_key: str, preview_key: str | None = None) -> None:
    for key in (storage_key, preview_key):
        if not key:
            continue
        try:
            asset_path(key).unlink(missing_ok=True)
        except InvalidImageError:
            pass


# --- video -----------------------------------------------------------------------------------
# We cannot re-encode without ffmpeg, so the MP4 container structure is validated strictly and
# files are served as video/mp4 with nosniff.

_MP4_BRANDS = {
    b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1", b"M4V ", b"dash",
}  # fmt: skip
_MP4_TOP_LEVEL = {
    b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide", b"uuid", b"meta",
    b"pdin", b"styp", b"sidx", b"moof", b"mfra", b"udta",
}  # fmt: skip


def _validate_mp4_stream(f: BinaryIO, total: int) -> None:
    if total > get_settings().max_video_bytes:
        raise InvalidImageError("video too large")
    if total < 16:
        raise InvalidImageError("not a valid video")
    offset, seen = 0, set()
    while offset < total:
        if offset + 8 > total:
            raise InvalidImageError("truncated box")
        f.seek(offset)
        head = f.read(16)
        size = int.from_bytes(head[0:4], "big")
        box = head[4:8]
        header = 8
        if size == 1:
            if offset + 16 > total:
                raise InvalidImageError("truncated box")
            size, header = int.from_bytes(head[8:16], "big"), 16
        elif size == 0:
            size = total - offset
        if size < header or offset + size > total:
            raise InvalidImageError("bad box size")
        if box not in _MP4_TOP_LEVEL:
            raise InvalidImageError("unexpected box")
        if offset == 0 and (box != b"ftyp" or head[8:12] not in _MP4_BRANDS):
            raise InvalidImageError("not an MP4")
        seen.add(box)
        offset += size
    if b"moov" not in seen or not ({b"mdat", b"moof"} & seen):
        raise InvalidImageError("incomplete MP4")


def validate_mp4(data: bytes) -> None:
    _validate_mp4_stream(io.BytesIO(data), len(data))


_MAX_MOOV_BYTES = 32 * 1024 * 1024


def _child_boxes(buf: bytes):
    """(type, payload) of each box inside `buf` (an already-read container box payload)."""
    offset = 0
    while offset + 8 <= len(buf):
        size = int.from_bytes(buf[offset : offset + 4], "big")
        box, header = buf[offset + 4 : offset + 8], 8
        if size == 1 and offset + 16 <= len(buf):
            size, header = int.from_bytes(buf[offset + 8 : offset + 16], "big"), 16
        elif size == 0:
            size = len(buf) - offset
        if size < header or offset + size > len(buf):
            return
        yield box, buf[offset + header : offset + size]
        offset += size


def _track_size(tkhd: bytes) -> tuple[int, int] | None:
    version = tkhd[0] if tkhd else 0
    pos = (4 + 32 + 52) if version == 1 else (4 + 20 + 52)  # version/flags + fields + matrix etc.
    if len(tkhd) < pos + 8:
        return None
    w = int.from_bytes(tkhd[pos : pos + 4], "big") >> 16  # 16.16 fixed point
    h = int.from_bytes(tkhd[pos + 4 : pos + 8], "big") >> 16
    return (w, h) if w > 0 and h > 0 else None


def probe_mp4_size(source: Path | bytes) -> tuple[int, int] | None:
    """(width, height) of the first video track, read from the MP4 header (no ffmpeg needed).

    This is the real size of the file, which is what the UI must show; providers' requested
    sizes are only a hint. Returns None when the header cannot be read.
    """
    try:
        if isinstance(source, bytes):
            f: BinaryIO = io.BytesIO(source)
            total = len(source)
        else:
            f = source.open("rb")
            total = source.stat().st_size
        with f:
            offset = 0
            while offset + 8 <= total:
                f.seek(offset)
                head = f.read(16)
                size = int.from_bytes(head[0:4], "big")
                box, header = head[4:8], 8
                if size == 1:
                    size, header = int.from_bytes(head[8:16], "big"), 16
                elif size == 0:
                    size = total - offset
                if size < header or offset + size > total:
                    return None
                if box == b"moov":
                    if size - header > _MAX_MOOV_BYTES:
                        return None
                    f.seek(offset + header)
                    moov = f.read(size - header)
                    for kind, payload in _child_boxes(moov):
                        if kind != b"trak":
                            continue
                        for sub, body in _child_boxes(payload):
                            if sub == b"tkhd" and (dims := _track_size(body)):
                                return dims
                    return None
                offset += size
    except (OSError, ValueError):
        return None
    return None


def store_video(data: bytes, width: int, height: int) -> StoredImage:
    validate_mp4(data)
    width, height = probe_mp4_size(data) or (width, height)  # the file's own size wins
    key = f"{secrets.token_hex(16)}.mp4"
    asset_path(key).write_bytes(data)
    return StoredImage(key, "video/mp4", width, height, len(data))


def store_video_file(path: Path, width: int, height: int) -> StoredImage:
    """Validate a downloaded MP4 on disk (no full read into memory) and move it into place."""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            _validate_mp4_stream(f, size)
        width, height = probe_mp4_size(path) or (width, height)  # the file's own size wins
        key = f"{secrets.token_hex(16)}.mp4"
        os.replace(path, asset_path(key))
        return StoredImage(key, "video/mp4", width, height, size)
    finally:
        path.unlink(missing_ok=True)
