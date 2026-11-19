# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import tempfile

from cryptography.fernet import Fernet

_TMP = tempfile.mkdtemp(prefix="aurevid-test-")
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP}/boot.db",
        "ASSET_DIR": f"{_TMP}/assets",
        "JWT_SECRET": "test-secret-" + "x" * 40,
        "BYOK_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "COOKIE_SECURE": "false",
        "CORS_ORIGINS": '["http://testserver"]',
        "MOCK_PROVIDER_ENABLED": "true",
        "POLLINATIONS_ENABLED": "false",
        "CLOUDFLARE_ENABLED": "true",
        "FAL_ENABLED": "false",
        "RUN_WORKER_IN_API": "false",
        "SIGNUP_CREDITS": "10",
        "TURNSTILE_SECRET": "",
        "CF_ACCOUNT_ID": "",
        "CF_API_TOKEN": "",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.ratelimit import reset_limits  # noqa: E402


@pytest.fixture(autouse=True)
async def fresh_db(tmp_path):
    db.configure_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with db.engine.begin() as conn:
        await conn.run_sync(db.Base.metadata.create_all)
    reset_limits()
    s = get_settings()
    saved = {k: getattr(s, k) for k in type(s).model_fields}  # keeps nested models as models
    s.asset_dir = str(tmp_path / "assets")
    yield
    for k, v in saved.items():
        setattr(s, k, v)
    await db.engine.dispose()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("av_csrf", "")}


async def make_user(email: str = "a@example.com", password: str = "correct horse battery"):
    client = _client()
    await client.get("/api/auth/csrf")
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "accept_terms": True},
        headers=csrf_headers(client),
    )
    assert r.status_code == 201, r.text
    return client, r.json()


@pytest.fixture
async def anon():
    async with _client() as c:
        yield c


@pytest.fixture
async def alice():
    client, _ = await make_user("alice@example.com")
    yield client
    await client.aclose()


@pytest.fixture
async def bob():
    client, _ = await make_user("bob@example.com")
    yield client
    await client.aclose()
