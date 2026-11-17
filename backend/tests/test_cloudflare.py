# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cloudflare adapter request shape (regression: Workers AI rejects unknown fields)."""

import base64
import json

import httpx
import pytest

from app.providers import cloudflare
from app.providers.base import Credentials, GenerationRequest, ProviderError

CREDS = Credentials({"account_id": "a" * 32, "api_token": "t"}, "user")


def _req():
    return GenerationRequest(
        "a red apple", "@cf/black-forest-labs/flux-1-schnell", "1:1", 1024, 1024, seed=42
    )


@pytest.fixture
def fake(monkeypatch):
    seen = []

    def install(status=200):
        def handler(request):
            seen.append(request)
            if status != 200:
                return httpx.Response(status, json={"errors": [{"message": "x"}]})
            return httpx.Response(
                200, json={"result": {"image": base64.b64encode(b"jpg").decode()}}
            )

        transport = httpx.MockTransport(handler)
        real = httpx.AsyncClient
        monkeypatch.setattr(
            cloudflare.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw)
        )

    return install, seen


async def test_body_has_only_documented_fields(fake):
    install, seen = fake
    install()
    out = await cloudflare.CloudflareProvider().generate(_req(), CREDS)
    assert out.data == b"jpg"
    assert set(json.loads(seen[0].content)) == {"prompt", "steps"}  # no "seed"
    assert seen[0].headers["authorization"] == "Bearer t"


async def test_client_errors_are_not_retried(fake):
    install, _ = fake
    install(400)
    with pytest.raises(ProviderError) as err:
        await cloudflare.CloudflareProvider().generate(_req(), CREDS)
    assert err.value.retryable is False
