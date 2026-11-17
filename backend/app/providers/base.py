# SPDX-License-Identifier: AGPL-3.0-or-later
"""The single interface every generation provider implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
SizeName = Literal["small", "medium", "large"]

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
    kind: Literal["image", "video"] = "image"
    license: str  # SPDX id or short name, see MODEL_LICENSES.md
    commercial_use: Literal["yes", "no", "unclear"]
    aspect_ratios: list[str]
    credit_cost: int  # credits per output image
    max_count: int = 4


class ProviderInfo(BaseModel):
    id: str
    name: str
    tier: Literal["free", "paid"]  # what the *end user* pays; shown in the UI
    byok: bool  # accepts the user's own key
    byok_fields: list[str] = []
    requires_key: bool  # cannot run without a key (server or user)
    models: list[ModelInfo]
    notes: str = ""


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


@dataclass
class GeneratedImage:
    data: bytes
    mime: str


class ProviderError(Exception):
    """`public` is safe to show to the user; never include keys or raw upstream bodies."""

    def __init__(self, public: str, *, retryable: bool = False):
        super().__init__(public)
        self.public = public
        self.retryable = retryable


class ImageProvider(ABC):
    info: ProviderInfo

    def model(self, model_id: str) -> ModelInfo | None:
        return next((m for m in self.info.models if m.id == model_id), None)

    def server_credentials(self) -> Credentials:
        return Credentials()

    def has_usable_credentials(self, creds: Credentials) -> bool:
        return not self.info.requires_key or creds.source != "none"

    @abstractmethod
    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedImage: ...
