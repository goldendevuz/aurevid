# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin-created public share links for generated media."""

from app import db
from app.images import asset_path
from app.models import Asset
from tests.conftest import csrf_headers, make_user
from tests.test_admin import _promote


async def _asset(user_id: str) -> str:
    key = "sharetest0123456789abcdef01234567.mp4"
    asset_path(key).write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 64)
    async with db.session_factory()() as s:
        a = Asset(
            user_id=user_id,
            source="generated",
            storage_key=key,
            mime="video/mp4",
            width=8,
            height=8,
            size_bytes=80,
        )
        s.add(a)
        await s.commit()
        return a.id


async def test_share_lifecycle(alice, anon):
    uid = await _promote(alice)
    aid = await _asset(uid)
    h = csrf_headers(alice)

    r = await alice.post(f"/api/admin/assets/{aid}/share", headers=h)
    assert r.status_code == 200
    token = r.json()["share_token"]
    assert len(token) >= 20
    # idempotent: same link again
    assert (await alice.post(f"/api/admin/assets/{aid}/share", headers=h)).json()[
        "share_token"
    ] == token

    listed = (await alice.get("/api/admin/media?kind=video&shared=true")).json()
    assert listed["total"] == 1 and listed["items"][0]["share_token"] == token

    pub = await anon.get(f"/api/s/{token}")  # no login
    assert pub.status_code == 200
    assert pub.headers["content-type"] == "video/mp4"
    assert "media-src 'self'" in pub.headers["content-security-policy"]

    assert (await alice.delete(f"/api/admin/assets/{aid}/share", headers=h)).status_code == 204
    assert (await anon.get(f"/api/s/{token}")).status_code == 404


async def test_unknown_token_404(anon):
    assert (await anon.get("/api/s/" + "a" * 32)).status_code == 404
    assert (await anon.get("/api/s/short")).status_code == 404


async def test_non_admin_cannot_share(alice):
    me = (await alice.get("/api/me")).json()
    aid = await _asset(me["id"])
    r = await alice.post(f"/api/admin/assets/{aid}/share", headers=csrf_headers(alice))
    assert r.status_code in (403, 404)
    bob, _ = await make_user("bob@example.com")
    assert (await bob.get("/api/admin/media")).status_code in (403, 404)
    await bob.aclose()
