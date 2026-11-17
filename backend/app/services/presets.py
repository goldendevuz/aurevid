# SPDX-License-Identifier: AGPL-3.0-or-later
"""Presets: JSON prompt templates loaded from app/presets/*.json and validated at startup."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.providers.base import AspectRatio

PRESET_DIR = Path(__file__).resolve().parent.parent / "presets"


class Preset(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]{3,64}$")
    name: str
    category: Literal["camera", "style", "marketing"]
    description: str
    prompt_template: str
    image_defaults: dict[str, AspectRatio] = {}
    video_params: dict[str, str | float | int] = {}

    @field_validator("prompt_template")
    @classmethod
    def _has_subject(cls, v: str) -> str:
        if v.count("{subject}") != 1:
            raise ValueError("prompt_template must contain {subject} exactly once")
        return v

    def render(self, subject: str) -> str:
        # Plain replacement, not str.format: user text can never inject format fields.
        return self.prompt_template.replace("{subject}", subject.strip())


@lru_cache
def load_presets() -> dict[str, Preset]:
    presets = {}
    for path in sorted(PRESET_DIR.glob("*.json")):
        preset = Preset.model_validate(json.loads(path.read_text(encoding="utf-8")))
        presets[preset.id] = preset
    return presets
