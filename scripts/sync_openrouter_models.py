#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sync public video models from OpenRouter to openrouter_models.json.

Public metadata only; requires no API key and never logs or prints secrets.
Idempotent: models are sorted by slug for stable diffs.
"""

import json
import sys
import urllib.request
from pathlib import Path

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/videos/models"
DEST_PATH = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "app"
    / "providers"
    / "openrouter_models.json"
)


def fetch_models() -> list[dict]:
    req = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={"User-Agent": "Aurevid-Model-Sync/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("data", [])


def sanitize_model(raw: dict) -> dict:
    return {
        "slug": raw.get("id"),
        "name": raw.get("name"),
        "description": raw.get("description"),
        "supported_resolutions": raw.get("supported_resolutions"),
        "supported_aspect_ratios": raw.get("supported_aspect_ratios"),
        "supported_sizes": raw.get("supported_sizes"),
        "supported_durations": raw.get("supported_durations"),
        "pricing_skus": raw.get("pricing_skus"),
        "generate_audio": raw.get("generate_audio"),
        "supported_frame_images": raw.get("supported_frame_images"),
    }


def sync() -> int:
    try:
        raw_models = fetch_models()
    except Exception as exc:  # noqa: BLE001
        print(f"Error fetching OpenRouter models: {exc}", file=sys.stderr)
        return 1

    clean_models = [sanitize_model(m) for m in raw_models if m.get("id")]
    clean_models.sort(key=lambda m: str(m["slug"]))

    DEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(clean_models, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Synced {len(clean_models)} models to {DEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(sync())
