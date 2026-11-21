# SPDX-License-Identifier: AGPL-3.0-or-later
"""The single interface every generation provider implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
SizeName = Literal["small", "medium", "large"]
UpscaleTarget = Literal["4k", "8k"]

# Extra credits per output for reaching 4K / 8K (CPU time for images, paid upscaler for video).
UPSCALE_CREDITS: dict[str, dict[str, int]] = {
    "image": {"4k": 1, "8k": 3},
    "video": {"4k": 4, "8k": 10},
}

# Base dimensions at "large"; all multiples of 64 for diffusion models.
ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "4:3": (1152, 896),
    "3:4": (896, 1152),
}
SIZE_SCALE: dict[str, float] = {"small": 0.5, "medium": 0.75, "large": 1.0}


def dimensions(aspect: str, size: str) -> tuple[int, int]:
    w, h = ASPECT_DIMENSIONS[aspect]
    scale = SIZE_SCALE[size]
    return int(w * scale) // 64 * 64, int(h * scale) // 64 * 64


class ModelInfo(BaseModel):
    id: str
    label: str
    kind: Literal["image", "video", "upscale"] = "image"
    license: str  # SPDX id or short name, see MODEL_LICENSES.md
    commercial_use: Literal["yes", "no", "unclear"]
    aspect_ratios: list[str]
    credit_cost: int  # credits per output (image or video)
    max_count: int = 4
    durations: list[int] = []  # video only: allowed lengths in seconds, first = default
    accepts_image: bool = False  # can take a start image (image-to-video)
    requires_image: bool = False
    # False = costly model: never runs on the owner's shared key, only on the user's own key
    server_key_ok: bool = True
    # Per-model generation limit (seconds) when it needs longer than the global video timeout
    timeout_s: int | None = None
    has_audio: bool = False  # video only: the model generates a soundtrack / speech
    upscale_targets: list[str] = []  # video: provider-side upscaling; images use the local upscaler


class ProviderInfo(BaseModel):
    id: str
    name: str
    tier: Literal["free", "paid"]  # what the *end user* pays; shown in the UI
    byok: bool  # accepts the user's own key
    byok_fields: list[str] = []
    requires_key: bool  # cannot run without a key (server or user)
    models: list[ModelInfo]
    notes: str = ""
    # Documented (or derived) daily output limit per credential, used as the learner's prior.
    daily_quota_prior: int | None = None
    key_url: str = ""  # where a user creates the key this provider needs
    key_guide_url: str = ""  # step-by-step guide
    track_quota: bool = True  # paid providers bill per use; no learning needed


@dataclass
class Credentials:
    values: dict[str, str] = field(default_factory=dict, repr=False)
    source: Literal["server", "user", "none"] = "none"


@dataclass
class GenerationRequest:
    prompt: str
    model: str
    aspect_ratio: str
    width: int
    height: int
    seed: int | None = None
    kind: Literal["image", "video"] = "image"
    size: str = "large"
    duration_s: int | None = None
    image: bytes | None = field(default=None, repr=False)  # JPEG start frame (image-to-video)
    upscale: str | None = None  # "4k" | "8k" (video adapters handle it themselves)
    workdir: Path | None = None  # where adapters may stream large downloads


@dataclass
class GeneratedMedia:
    data: bytes
    mime: str
    path: Path | None = None  # large results are streamed to disk instead of held in memory


GeneratedImage = GeneratedMedia  # backwards-compatible name


class ProviderError(Exception):
    """`public` is safe to show to the user; never include keys or raw upstream bodies.

    A single short, sanitised upstream message field is fine (see cloudflare._error_detail).
    """

    def __init__(self, public: str, *, retryable: bool = False, quota: bool = False):
        super().__init__(public)
        self.public = public
        self.retryable = retryable
        self.quota = quota  # provider-side limit hit (feeds the quota learner)


class ImageProvider(ABC):
    info: ProviderInfo

    def model(self, model_id: str) -> ModelInfo | None:
        return next((m for m in self.info.models if m.id == model_id), None)

    def server_credentials(self) -> Credentials:
        return Credentials()

    def has_usable_credentials(self, creds: Credentials) -> bool:
        return not self.info.requires_key or creds.source != "none"

    @abstractmethod
    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedMedia: ...
