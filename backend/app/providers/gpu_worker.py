# SPDX-License-Identifier: AGPL-3.0-or-later
"""Wan 2.2 text/image-to-video on a GPU machine the owner runs (deploy/gpu-worker/).

The server never executes these jobs: they stay queued until the remote worker claims them over
`/api/gpu-worker/*` (routers/gpu_worker.py). Nobody pays for the GPU time per clip, so the price
shown to users is 0 credits (the daily job limit still applies). Off unless GPU_WORKER_TOKEN is set.
"""

from app.providers.base import (
    Credentials,
    GeneratedMedia,
    GenerationRequest,
    ImageProvider,
    ModelInfo,
    ProviderError,
    ProviderInfo,
)

PROVIDER_ID = "gpu_worker"
WAN = "wan-2.2-ti2v-5b"
# (width, height) per ratio: multiples of 32 for Wan 2.2 5B, small so a clip is quick.
SIZES = {"16:9": (832, 480), "9:16": (480, 832), "1:1": (640, 640)}
FRAMES = {5: 121, 3: 73}  # 24 fps, 4k+1 frames
FPS = 24


class GpuWorkerProvider(ImageProvider):
    info = ProviderInfo(
        id=PROVIDER_ID,
        name="Aurevid GPU (Wan 2.2)",
        tier="free",
        byok=False,
        requires_key=False,
        track_quota=False,
        models=[
            ModelInfo(
                id=WAN,
                label="Wan 2.2 TI2V-5B text/image-to-video (GPU worker)",
                kind="video",
                license="Apache-2.0",
                commercial_use="yes",
                aspect_ratios=list(SIZES),
                credit_cost=0,
                max_count=1,
                durations=[5, 3],
                accepts_image=True,
                has_audio=False,  # Wan 2.2 TI2V-5B makes silent clips
            )
        ],
        notes="Free: runs on the owner's own GPU, so a clip can wait in the queue until the "
        "GPU machine is online.",
    )

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedMedia:
        # Reached only if the server worker picked the job up by mistake (queue.py prevents it).
        raise ProviderError("This video is made by a remote GPU worker")
