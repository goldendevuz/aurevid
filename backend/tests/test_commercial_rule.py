# SPDX-License-Identifier: AGPL-3.0-or-later
"""Owner rule: only models whose commercial use is clearly allowed are offered."""

import pytest

from app.config import Settings, get_settings
from app.providers.fal import KLING_I2V, KLING_T2V
from app.providers.registry import enabled_providers
from tests.conftest import csrf_headers


def test_defaults_hide_every_unclear_model():
    s = get_settings()
    s.fal_enabled = True
    s.pollinations_video_enabled = True  # even if someone switches the adapter on
    providers = enabled_providers()
    for p in providers.values():
        for m in p.info.models:
            assert m.commercial_use == "yes", (p.info.id, m.id)
    assert "pollinations_video" not in providers
    fal = providers["fal"]
    assert fal.model(KLING_T2V) is None and fal.model(KLING_I2V) is None
    assert fal.model("fal-ai/wan/v2.2-5b/text-to-video") is not None


def test_class_catalogue_is_not_mutated():
    from app.providers.fal import FalProvider

    get_settings().fal_enabled = True
    enabled_providers()
    assert FalProvider().model(KLING_T2V) is not None  # filtering is per instance only


def test_unclear_models_cannot_be_enabled_in_prod():
    with pytest.raises(ValueError, match="ALLOW_UNCLEAR_MODELS"):
        Settings(
            app_env="prod",
            jwt_secret="x" * 40,
            byok_encryption_key="k",
            cookie_secure=True,
            mock_provider_enabled=False,
            allow_unclear_models=True,
        )


async def test_job_for_hidden_model_is_refused(alice):
    get_settings().fal_enabled = True
    r = await alice.post(
        "/api/jobs",
        json={"provider": "fal", "model": KLING_T2V, "prompt": "a calm sea", "kind": "video"},
        headers=csrf_headers(alice),
    )
    assert r.status_code in (400, 404, 422), r.text
