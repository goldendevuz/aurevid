# SPDX-License-Identifier: AGPL-3.0-or-later
"""Image validation by content (magic bytes via Pillow), re-encoding and safe storage."""

import io
import secrets
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import get_settings

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class InvalidImageError(ValueError):
    pass


@dataclass
class StoredImage:
    storage_key: str
    mime: str
    width: int
    height: int
    size_bytes: int


def asset_root() -> Path:
    root = Path(get_settings().asset_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def asset_path(storage_key: str) -> Path:
    """Map a server-generated key to a path, refusing anything that escapes the asset root."""
    if not storage_key or "/" in storage_key or "\\" in storage_key or storage_key.startswith("."):
        raise InvalidImageError("bad storage key")
    root = asset_root()
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise InvalidImageError("bad storage key")
    return path


def reencode_image(data: bytes) -> tuple[bytes, int, int]:
    """Validate the bytes really are an allowed image and re-encode them to clean WebP.

    Re-encoding drops metadata (EXIF/GPS), embedded payloads and polyglot tricks.
    """
    s = get_settings()
    if not data:
        raise InvalidImageError("empty file")
    if len(data) > s.max_upload_bytes:
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
            clean = img.convert(mode)
            out = io.BytesIO()
            clean.save(out, format="WEBP", quality=90, method=4)
            return out.getvalue(), clean.width, clean.height
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise InvalidImageError("not a valid image") from exc


def store_image(data: bytes) -> StoredImage:
    clean, width, height = reencode_image(data)
    key = f"{secrets.token_hex(16)}.webp"
    path = asset_path(key)
    path.write_bytes(clean)
    return StoredImage(key, "image/webp", width, height, len(clean))


def delete_stored(storage_key: str) -> None:
    try:
        asset_path(storage_key).unlink(missing_ok=True)
    except InvalidImageError:
        pass
