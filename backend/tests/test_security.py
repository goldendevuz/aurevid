# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import hmac
import io
import time

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select

from app import db
from app.config import Settings
from app.images import InvalidImageError, asset_path, reencode_image
from app.models import ProviderKey
from app.moderation import moderator
from app.ssrf import UnsafeURLError, resolve_public_ip, validate_url
from app.webhooks import WebhookRejected, claim_event, verify_signature
from tests.conftest import csrf_headers


def _png(exif: bool = False) -> bytes:
    img = Image.new("RGB", (32, 24), (10, 120, 200))
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretCam"  # Make
        img.save(buf, format="JPEG", exif=ex.tobytes())
    else:
        img.save(buf, format="PNG")
    return buf.getvalue()


# --- headers / CORS / config ---------------------------------------------------------------


async def test_security_headers(anon):
    r = await anon.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]


async def test_cors_allowlist(anon):
    ok = await anon.options(
        "/api/me",
        headers={"Origin": "http://testserver", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://testserver"
    bad = await anon.options(
        "/api/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers


def test_cors_wildcard_and_weak_prod_config_refused():
    with pytest.raises(ValidationError):
        Settings(cors_origins=["*"])
    with pytest.raises(ValidationError):
        Settings(app_env="prod", jwt_secret="short", byok_encryption_key="k")
    with pytest.raises(ValidationError):
        Settings(
            app_env="prod", jwt_secret="x" * 40, byok_encryption_key="k", mock_provider_enabled=True
        )


# --- SSRF ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.png",  # http not allowed by default
        "file:///etc/passwd",
        "gopher://example.com/",
        "https://user:pw@example.com/",
        "https://example.com:8443/",
        "https:///nohost",
    ],
)
def test_ssrf_url_validation_rejects(url):
    with pytest.raises(UnsafeURLError):
        validate_url(url)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "10.0.0.5",
        "169.254.169.254",
        "192.168.1.1",
        "::1",
        "::ffff:127.0.0.1",
        "0.0.0.0",
        "100.64.0.1",
        "localhost",
    ],
)
async def test_ssrf_blocks_internal_addresses(host):
    with pytest.raises(UnsafeURLError):
        await resolve_public_ip(host)


async def test_ssrf_allows_public_literal():
    assert await resolve_public_ip("1.1.1.1") == "1.1.1.1"


# --- images / uploads ----------------------------------------------------------------------


def test_reencode_strips_metadata_and_outputs_webp():
    out, w, h = reencode_image(_png(exif=True))
    assert out[:4] == b"RIFF" and (w, h) == (32, 24)
    assert b"SecretCam" not in out


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"<svg onload=alert(1)>",
        b"GIF89a" + b"\x00" * 20,
        b"%PDF-1.4 fake",
        b"\x89PNG\r\n\x1a\nbroken",
    ],
)
def test_reencode_rejects_non_images(payload):
    with pytest.raises(InvalidImageError):
        reencode_image(payload)


@pytest.mark.parametrize("key", ["../etc/passwd", "a/b.webp", ".hidden", "", "..\\x"])
def test_asset_path_traversal_blocked(key):
    with pytest.raises(InvalidImageError):
        asset_path(key)


async def test_upload_checks_content_not_name(alice):
    h = csrf_headers(alice)
    bad = await alice.post(
        "/api/assets/upload",
        files={"file": ("cat.png", b"<?php system($_GET[c]); ?>", "image/png")},
        headers=h,
    )
    assert bad.status_code == 415
    good = await alice.post(
        "/api/assets/upload",
        files={"file": ("../../evil.exe", _png(), "application/x-msdownload")},
        headers=h,
    )
    assert good.status_code == 201
    body = good.json()
    assert body["mime"] == "image/webp" and "evil" not in body["url"]


async def test_upload_size_limit(alice):
    from app.config import get_settings

    get_settings().max_upload_bytes = 50
    r = await alice.post(
        "/api/assets/upload",
        files={"file": ("a.png", _png(), "image/png")},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 413


# --- BYOK ----------------------------------------------------------------------------------


async def test_byok_key_encrypted_and_never_returned(alice):
    secret = "cf-token-SUPERSECRET-value"
    r = await alice.put(
        "/api/me/keys/cloudflare",
        json={"values": {"account_id": "a" * 32, "api_token": secret}},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 200 and secret not in r.text
    for path in ("/api/me/keys", "/api/providers", "/api/me", "/api/me/export"):
        assert secret not in (await alice.get(path)).text
    providers = {p["id"]: p for p in (await alice.get("/api/providers")).json()}
    assert providers["cloudflare"]["available"] and providers["cloudflare"]["key_source"] == "user"
    async with db.session_factory()() as s:
        row = (await s.execute(select(ProviderKey))).scalar_one()
    assert secret not in row.ciphertext


async def test_byok_rejects_unknown_fields(alice):
    r = await alice.put(
        "/api/me/keys/cloudflare", json={"values": {"evil": "x"}}, headers=csrf_headers(alice)
    )
    assert r.status_code == 422


# --- webhooks ------------------------------------------------------------------------------


def _sign(secret: str, ts: int, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def test_webhook_signature_and_replay_window():
    body, now = b'{"id":"evt_1"}', int(time.time())
    verify_signature("s3cret", body, _sign("s3cret", now, body), str(now))
    with pytest.raises(WebhookRejected):
        verify_signature("s3cret", body, _sign("other", now, body), str(now))
    with pytest.raises(WebhookRejected):
        verify_signature("s3cret", body + b" ", _sign("s3cret", now, body), str(now))
    old = now - 3600
    with pytest.raises(WebhookRejected):
        verify_signature("s3cret", body, _sign("s3cret", old, body), str(old))
    with pytest.raises(WebhookRejected):
        verify_signature("", body, "x", str(now))


async def test_webhook_event_idempotency():
    async with db.session_factory()() as s:
        assert await claim_event(s, "test", "evt_1") is True
        assert await claim_event(s, "test", "evt_1") is False
        await s.commit()


# --- moderation ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt,allowed",
    [
        ("a cozy coffee shop at dawn", True),
        ("product photo of running shoes", True),
        ("explicit nsfw scene", False),
        ("n​ude teen", False),
    ],
)
def test_moderation(prompt, allowed):
    assert moderator.check_prompt(prompt).allowed is allowed
