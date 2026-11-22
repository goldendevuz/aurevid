# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline demo provider for development and tests: draws a deterministic gradient.

Never enabled in production (config validation refuses it).
"""

import asyncio
import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw

from app.providers.base import (
    Credentials,
    GeneratedImage,
    GenerationRequest,
    ImageProvider,
    ModelInfo,
    ProviderError,
    ProviderInfo,
)

_DEMO_VIDEO = Path(__file__).resolve().parent / "media" / "demo.mp4"


class MockProvider(ImageProvider):
    info = ProviderInfo(
        id="demo",
        name="Offline demo",
        tier="free",
        byok=False,
        requires_key=False,
        models=[
            ModelInfo(
                id="gradient",
                label="Gradient sketch (offline)",
                license="AGPL-3.0-or-later (our code)",
                commercial_use="yes",
                aspect_ratios=["1:1", "16:9", "9:16", "4:3", "3:4"],
                credit_cost=1,
            ),
            ModelInfo(
                id="gradient-hd",
                label="Gradient master (offline, publish quality)",
                license="AGPL-3.0-or-later (our code)",
                commercial_use="yes",
                aspect_ratios=["1:1", "16:9", "9:16", "4:3", "3:4"],
                credit_cost=1,
                publish_max_side=1920,
            ),
            ModelInfo(
                id="loop",
                label="Amber loop (offline video)",
                kind="video",
                license="AGPL-3.0-or-later (our clip)",
                commercial_use="yes",
                aspect_ratios=["1:1", "16:9", "9:16"],
                # The demo clip is always 320x320, whatever the format asked for.
                fixed_dimensions={"1:1": (320, 320), "16:9": (320, 320), "9:16": (320, 320)},
                credit_cost=2,
                max_count=1,
                durations=[3, 5],
                accepts_image=True,
            ),
        ],
        notes="Development only. Draws a placeholder; no AI model involved.",
    )

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedImage:
        if "__fail__" in req.prompt:
            raise ProviderError("Demo provider failure (requested)")
        if "__partial__" in req.prompt and (req.seed or 0) % 2 == 1:
            raise ProviderError("Demo provider partial failure (requested)")
        await asyncio.sleep(0.2)
        if req.kind == "video":
            # A 3-second clip we rendered ourselves (ffmpeg "gradients" source, 320x320).
            return GeneratedImage(_DEMO_VIDEO.read_bytes(), "video/mp4")
        digest = hashlib.sha256(f"{req.prompt}|{req.seed}".encode()).digest()
        w, h = max(64, req.width // 4), max(64, req.height // 4)
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        c1, c2 = digest[:3], digest[3:6]
        for y in range(h):
            t = y / max(1, h - 1)
            color = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
            draw.line([(0, y), (w, y)], fill=color)
        r = min(w, h) // 4
        draw.ellipse([w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r], outline=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return GeneratedImage(buf.getvalue(), "image/png")
