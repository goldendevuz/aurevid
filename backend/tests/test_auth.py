# SPDX-License-Identifier: AGPL-3.0-or-later
from sqlalchemy import select

from app import db
from app.models import RefreshToken, User
from tests.conftest import _client, csrf_headers, make_user


async def test_register_sets_secure_cookies_and_grants_credits():
    client, user = await make_user("new@example.com")
    try:
        assert user["credit_balance"] == 10
        assert "password_hash" not in user
        me = await client.get("/api/me")
        assert me.status_code == 200 and me.json()["email"] == "new@example.com"
        set_cookie = client.cookies.jar
        names = {c.name: c for c in set_cookie}
        assert names["av_access"].has_nonstandard_attr("HttpOnly")
        assert names["av_refresh"].has_nonstandard_attr("HttpOnly")
        assert names["av_refresh"].path == "/api/auth"
        assert not names["av_csrf"].has_nonstandard_attr("HttpOnly")
    finally:
        await client.aclose()


async def test_password_is_argon2id_hashed():
    client, _ = await make_user("hash@example.com", "a very long passphrase")
    await client.aclose()
    async with db.session_factory()() as s:
        user = (await s.execute(select(User))).scalar_one()
    assert user.password_hash.startswith("$argon2id$")


async def test_duplicate_email_is_generic(alice):
    client = _client()
    async with client:
        await client.get("/api/auth/csrf")
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "ALICE@example.com",
                "password": "another password",
                "accept_terms": True,
            },
            headers=csrf_headers(client),
        )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "registration_failed"


async def test_register_validation(anon):
    await anon.get("/api/auth/csrf")
    h = csrf_headers(anon)
    short = {"email": "x@example.com", "password": "short", "accept_terms": True}
    assert (await anon.post("/api/auth/register", json=short, headers=h)).status_code == 422
    no_terms = {"email": "x@example.com", "password": "long enough pw", "accept_terms": False}
    assert (await anon.post("/api/auth/register", json=no_terms, headers=h)).status_code == 422
    extra = {**short, "password": "long enough pw", "is_admin": True}
    r = await anon.post("/api/auth/register", json=extra, headers=h)
    assert r.status_code == 422  # unknown fields are rejected (no mass assignment)
    assert "long enough pw" not in r.text  # input is not echoed back


async def test_login_wrong_password_and_unknown_user(alice, anon):
    await anon.get("/api/auth/csrf")
    h = csrf_headers(anon)
    bad = await anon.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "nope"}, headers=h
    )
    unknown = await anon.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "nope"}, headers=h
    )
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()
    ok = await anon.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery"},
        headers=h,
    )
    assert ok.status_code == 200


async def test_csrf_required_for_unsafe_methods(alice):
    r = await alice.post("/api/auth/logout")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "csrf_failed"
    r = await alice.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"})
    assert r.status_code == 403


async def test_foreign_origin_rejected(alice):
    h = {**csrf_headers(alice), "Origin": "https://evil.example"}
    r = await alice.post("/api/auth/logout", headers=h)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "bad_origin"


async def test_unauthenticated_requests_rejected(anon):
    for path in ("/api/me", "/api/jobs", "/api/credits", "/api/providers"):
        assert (await anon.get(path)).status_code == 401


async def test_refresh_rotation_and_reuse_detection(alice):
    old_refresh = alice.cookies.get("av_refresh", path="/api/auth")
    r = await alice.post("/api/auth/refresh", headers=csrf_headers(alice))
    assert r.status_code == 204
    new_refresh = alice.cookies.get("av_refresh", path="/api/auth")
    assert new_refresh and new_refresh != old_refresh

    # An attacker replays the old (rotated) token: the whole family is revoked.
    thief = _client()
    async with thief:
        await thief.get("/api/auth/csrf")
        thief.cookies.set("av_refresh", old_refresh, domain="testserver.local", path="/api/auth")
        replay = await thief.post("/api/auth/refresh", headers=csrf_headers(thief))
        assert replay.status_code == 401

    r = await alice.post("/api/auth/refresh", headers=csrf_headers(alice))
    assert r.status_code == 401  # legitimate holder must log in again
    async with db.session_factory()() as s:
        live = (
            (await s.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))))
            .scalars()
            .all()
        )
    assert live == []


async def test_logout_revokes_refresh(alice):
    r = await alice.post("/api/auth/logout", headers=csrf_headers(alice))
    assert r.status_code == 204
    assert (await alice.get("/api/me")).status_code == 401


async def test_tampered_access_token_rejected(alice):
    token = alice.cookies.get("av_access")
    alice.cookies.set("av_access", token[:-2] + "xx", domain="testserver.local")
    assert (await alice.get("/api/me")).status_code == 401


async def test_blocked_user_cannot_use_api(alice):
    async with db.session_factory()() as s:
        user = (await s.execute(select(User))).scalar_one()
        user.is_blocked = True
        await s.commit()
    r = await alice.get("/api/me")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "account_blocked"


async def test_login_rate_limited(anon):
    await anon.get("/api/auth/csrf")
    h = csrf_headers(anon)
    codes = [
        (
            await anon.post(
                "/api/auth/login", json={"email": "z@example.com", "password": "x"}, headers=h
            )
        ).status_code
        for _ in range(12)
    ]
    assert codes[-1] == 429
