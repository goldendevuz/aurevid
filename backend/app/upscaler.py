# SPDX-License-Identifier: AGPL-3.0-or-later
"""Free, local AI image upscaling to 4K / 8K (Real-ESRGAN realesr-general-x4v3, CPU, ONNX).

Model weights: BSD-3-Clause, (c) 2021 Xintao Wang; converted by scripts/convert_realesrgan.py.
"4K" / "8K" mean the long side reaches 3840 / 7680 px (aspect ratio kept).

The network is a 4x super-resolution model. The source is always resized (Lanczos) to exactly
target/4 first and the network adds the detail in one 4x step. That bounds the work: the network
never sees more than 1920x1920 px (8K square), so CPU time and memory (~200 MB) stay predictable,
whatever the input size. Work runs in overlapping tiles with a deadline checked between tiles.
"""

import os
import time
from functools import lru_cache

# Privacy: ONNX Runtime >= 1.30 initialises usage telemetry at import time on Linux; this must be
# set before the first import (the Dockerfile sets it too).
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import get_settings

MODEL_PATH = Path(__file__).resolve().parent / "upscale" / "realesr-general-x4v3.onnx"
TARGET_LONG_SIDE = {"4k": 3840, "8k": 7680}
TILE = 192
PAD = 16  # context around each tile, hides seams


def available() -> bool:
    return get_settings().upscaler_enabled and MODEL_PATH.exists()


class UpscaleTimeout(TimeoutError):
    pass


@lru_cache
def _session():
    import onnxruntime as ort  # imported lazily: only workers need it

    if hasattr(ort, "disable_telemetry_events"):
        ort.disable_telemetry_events()  # privacy: no usage telemetry from the runtime
    opts = ort.SessionOptions()
    threads = get_settings().upscaler_threads or max(1, (os.cpu_count() or 2) - 1)
    opts.intra_op_num_threads = threads
    return ort.InferenceSession(str(MODEL_PATH), opts, providers=["CPUExecutionProvider"])


def ai_x4(img: Image.Image, deadline: float | None = None) -> Image.Image:
    """Run the 4x network over an RGB image in padded tiles."""
    src = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    h, w, _ = src.shape
    out = np.empty((h * 4, w * 4, 3), dtype=np.uint8)
    session = _session()
    for y in range(0, h, TILE):
        for x in range(0, w, TILE):
            if deadline is not None and time.monotonic() > deadline:
                raise UpscaleTimeout("upscaling took too long")
            y0, x0 = max(0, y - PAD), max(0, x - PAD)
            y1, x1 = min(h, y + TILE + PAD), min(w, x + TILE + PAD)
            tile = np.ascontiguousarray(src[y0:y1, x0:x1].transpose(2, 0, 1)[None])
            res = session.run(None, {"input": tile})[0][0].transpose(1, 2, 0)
            th, tw = min(TILE, h - y) * 4, min(TILE, w - x) * 4
            oy, ox = (y - y0) * 4, (x - x0) * 4
            block = np.clip(res[oy : oy + th, ox : ox + tw], 0.0, 1.0)
            out[y * 4 : y * 4 + th, x * 4 : x * 4 + tw] = (block * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def target_size(size: tuple[int, int], target: str) -> tuple[int, int]:
    w, h = size
    scale = TARGET_LONG_SIDE[target] / max(w, h)
    return max(1, round(w * scale)), max(1, round(h * scale))


def upscale(img: Image.Image, target: str, timeout: float | None = None) -> Image.Image:
    """Upscale so the long side reaches the target. Never downscales."""
    final = target_size(img.size, target)
    if final[0] <= img.width:
        return img
    deadline = time.monotonic() + timeout if timeout else None
    alpha = img.getchannel("A") if img.mode == "RGBA" else None
    # Bounded work: the network always gets exactly final/4 (resized up or down with Lanczos).
    base = (max(1, round(final[0] / 4)), max(1, round(final[1] / 4)))
    rgb = img.convert("RGB")
    if rgb.size != base:
        rgb = rgb.resize(base, Image.Resampling.LANCZOS)
    up = ai_x4(rgb, deadline)
    if up.size != final:
        up = up.resize(final, Image.Resampling.LANCZOS)
    if alpha is not None:
        up.putalpha(alpha.resize(final, Image.Resampling.LANCZOS))
    return up
