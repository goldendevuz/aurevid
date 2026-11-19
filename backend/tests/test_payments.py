# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional credit packs: fake gateway flow, webhook safety, reconciliation, inPAY adapter."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update

from app import db
from app.config import Settings, get_settings
from app.models import CreditLedger, PaymentOrder, User
from app.services.payments import fake
from app.services.payments import orders as payment_orders
from app.services.payments.base import GatewayError, parse_amount
from app.services.payments.inpay import InpayGateway
from tests.conftest import csrf_headers

CALLBACK = "/api/payments/inpay/callback"
SECRET = "merchant-secret-tok-123"


@pytest.fixture(autouse=True)
def payments_on():
    s = get_settings()
    s.payments_provider = "fake"
    s.public_base_url = "https://aurevid.test"
    fake.reset()
    fake.autopay = False
    yield
    fake.reset()
    fake.autopay = True


async def _balance(client) -> int:
    return (await client.get("/api/credits")).json()["balance"]


async def _buy(client, pack_id="small"):
    return await client.post(
        "/api/payments/orders", json={"pack_id": pack_id}, headers=csrf_headers(client)
    )


async def _order(order_id) -> PaymentOrder:
    async with db.session_factory()() as s:
        return await s.get(PaymentOrder, order_id)


async def _as_inpay(order_id) -> str:
    """Pretend an order came from inPAY so the inPAY callback path can find it."""
    o = await _order(order_id)
    async with db.session_factory()() as s:
        await s.execute(
            update(PaymentOrder).where(PaymentOrder.id == order_id).values(provider="inpay")
        )
        await s.commit()
    return o.provider_order_id


class _FakeAsInpay(fake.FakeGateway):
    name = "inpay"


@pytest.fixture
def inpay_named(monkeypatch):
    """The fake gateway answering as "inpay", so the inPAY callback path can be exercised."""
    gw = _FakeAsInpay("https://aurevid.test")
    monkeypatch.setattr(payment_orders, "get_gateway", lambda: gw)
    return gw


async def test_packs_listed_and_disabled_by_default(anon):
    get_settings().payments_provider = "none"
    r = (await anon.get("/api/payments/packs")).json()
    assert r["enabled"] is False
    assert [p["credits"] for p in r["packs"]] == [100, 300, 1000]
    assert Settings().payments_provider == "none"


async def test_disabled_returns_503(alice):
    get_settings().payments_provider = "none"
    r = await _buy(alice)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "payments_disabled"


async def test_order_requires_auth_csrf_and_known_pack(anon, alice):
    assert (await anon.post("/api/payments/orders", json={"pack_id": "small"})).status_code == 403
    r = await alice.post("/api/payments/orders", json={"pack_id": "small"})
    assert r.status_code == 403  # no CSRF header
    r = await _buy(alice, "nope")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "unknown_pack"


async def test_full_flow_with_fake_gateway(alice):
    before = await _balance(alice)
    r = await _buy(alice)
    assert r.status_code == 201, r.text
    order_id = r.json()["order_id"]
    assert r.json()["pay_url"].startswith("https://aurevid.test/credits?order=")
    o = await _order(order_id)
    assert o.status == "pending" and o.amount_uzs == 15_000

    got = (await alice.get(f"/api/payments/orders/{order_id}")).json()
    assert got["status"] == "pending"

    fake.settle(o.provider_order_id)
    # Polling re-checks only every ~10 s: age the last check.
    async with db.session_factory()() as s:
        await s.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order_id)
            .values(last_checked_at=datetime.now(UTC) - timedelta(seconds=30))
        )
        await s.commit()
    got = (await alice.get(f"/api/payments/orders/{order_id}")).json()
    assert got["status"] == "paid" and got["paid_at"]
    assert await _balance(alice) == before + 100
    ledger = (await alice.get("/api/credits")).json()["ledger"]
    assert ledger[0]["reason"] == "purchase" and ledger[0]["delta"] == 100
    listed = (await alice.get("/api/payments/orders")).json()
    assert [o["id"] for o in listed] == [order_id]
    assert "pay_url" not in listed[0] and "provider_order_id" not in listed[0]


async def test_webhook_triggers_verified_credit_and_replay_is_idempotent(alice, anon, inpay_named):
    order_id = (await _buy(alice)).json()["order_id"]
    pid = await _as_inpay(order_id)
    fake.settle(pid)
    before = await _balance(alice)
    payload = {"order_id": pid, "status": "success", "amount": 15000, "transaction_id": "t1"}
    r = await anon.post(CALLBACK, json=payload)  # no cookies, no CSRF: exempt by exact path
    assert r.status_code == 200
    for _ in range(3):  # replays, including after the re-check window
        async with db.session_factory()() as s:
            await s.execute(
                update(PaymentOrder)
                .where(PaymentOrder.id == order_id)
                .values(last_checked_at=datetime.now(UTC) - timedelta(minutes=1))
            )
            await s.commit()
        assert (await anon.post(CALLBACK, json=payload)).status_code == 200
    # Direct concurrent settles cannot double-credit either.
    result = await inpay_named.check(pid)

    async def settle():
        async with db.session_factory()() as s:
            await payment_orders.apply_result(s, order_id, result)

    await asyncio.gather(*(settle() for _ in range(5)))
    assert await _balance(alice) == before + 100
    async with db.session_factory()() as s:
        n = (
            await s.execute(
                select(func.count()).where(CreditLedger.idempotency_key == f"purchase:{order_id}")
            )
        ).scalar_one()
    assert n == 1
    assert (await _order(order_id)).status == "paid"


async def test_webhook_alone_never_credits(alice, anon, inpay_named):
    """The callback claims success, but the gateway says pending: nothing is credited."""
    order_id = (await _buy(alice)).json()["order_id"]
    pid = await _as_inpay(order_id)
    before = await _balance(alice)
    r = await anon.post(CALLBACK, json={"order_id": pid, "status": "success", "amount": 15000})
    assert r.status_code == 200
    assert await _balance(alice) == before
    assert (await _order(order_id)).status == "pending"


async def test_amount_mismatch_not_credited(alice):
    order_id = (await _buy(alice)).json()["order_id"]
    o = await _order(order_id)
    fake.settle(o.provider_order_id, amount=1000)
    before = await _balance(alice)
    async with db.session_factory()() as s:
        status = await payment_orders.verify(s, await s.get(PaymentOrder, order_id))
    assert status == "failed"
    assert await _balance(alice) == before


@pytest.mark.parametrize(
    "body",
    [
        b'{"order_id": "does-not-exist", "status": "success", "amount": 15000}',
        b"not json at all",
        b'{"order_id": {"$ne": 1}}',
        b"[]",
        b"",
    ],
)
async def test_unknown_or_junk_callback_is_ignored_with_200(anon, body):
    r = await anon.post(CALLBACK, content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_order_idor(alice, bob):
    order_id = (await _buy(alice)).json()["order_id"]
    assert (await bob.get(f"/api/payments/orders/{order_id}")).status_code == 404
    assert (await bob.get("/api/payments/orders/nope")).status_code == 404
    assert (await bob.get("/api/payments/orders")).json() == []


async def test_gateway_failure_returns_502_and_marks_failed(alice, monkeypatch):
    import app.routers.payments as router_mod

    class Broken(fake.FakeGateway):
        async def create_order(self, *a, **k):
            raise GatewayError("inpay create failed (HTTP 500)")

    monkeypatch.setattr(router_mod, "get_gateway", lambda: Broken())
    r = await _buy(alice)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "payment_gateway_error"
    async with db.session_factory()() as s:
        assert (await s.execute(select(PaymentOrder.status))).scalar_one() == "failed"


async def test_reconciliation_credits_missed_webhook_and_expires_old(alice):
    before = await _balance(alice)
    paid_id = (await _buy(alice)).json()["order_id"]
    young_id = (await _buy(alice)).json()["order_id"]
    old_id = (await _buy(alice)).json()["order_id"]
    for oid in (paid_id, young_id):
        fake.settle((await _order(oid)).provider_order_id)
    now = datetime.now(UTC)
    async with db.session_factory()() as s:
        for oid, age in ((paid_id, timedelta(minutes=5)), (old_id, timedelta(hours=25))):
            await s.execute(
                update(PaymentOrder).where(PaymentOrder.id == oid).values(created_at=now - age)
            )
        await s.commit()
    await payment_orders.reconcile()
    assert (await _order(paid_id)).status == "paid"
    assert (await _order(young_id)).status == "pending"  # younger than 2 min: left alone
    assert (await _order(old_id)).status == "expired"
    assert await _balance(alice) == before + 100
    await payment_orders.reconcile()  # running again changes nothing
    assert await _balance(alice) == before + 100


async def test_late_payment_on_expired_order_is_still_credited(alice):
    order_id = (await _buy(alice)).json()["order_id"]
    async with db.session_factory()() as s:
        await s.execute(
            update(PaymentOrder).where(PaymentOrder.id == order_id).values(status="expired")
        )
        await s.commit()
    before = await _balance(alice)
    fake.settle((await _order(order_id)).provider_order_id)
    async with db.session_factory()() as s:
        await payment_orders.verify(s, await s.get(PaymentOrder, order_id))
    assert await _balance(alice) == before + 100


async def test_deleting_account_keeps_order_detached(alice):
    order_id = (await _buy(alice)).json()["order_id"]
    r = await alice.request(
        "DELETE",
        "/api/me",
        json={"password": "correct horse battery"},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 204
    assert (await _order(order_id)).user_id is None


async def test_admin_payments_list_and_revenue(alice, bob):
    order_id = (await _buy(alice)).json()["order_id"]
    fake.settle((await _order(order_id)).provider_order_id)
    async with db.session_factory()() as s:
        await payment_orders.verify(s, await s.get(PaymentOrder, order_id))
    await _buy(alice, "medium")
    assert (await bob.get("/api/admin/payments")).status_code == 404
    me = (await alice.get("/api/me")).json()
    async with db.session_factory()() as s:
        (await s.get(User, me["id"])).is_admin = True
        await s.commit()
    r = (await alice.get("/api/admin/payments?status=paid&q=alice")).json()
    assert r["total"] == 1 and r["items"][0]["user_email"] == "alice@example.com"
    assert r["revenue"]["all"] == {"orders": 1, "amount_uzs": 15000, "credits": 100}
    assert r["revenue"]["today"]["amount_uzs"] == 15000
    assert r["by_status"] == {"paid": 1, "pending": 1}


def test_settings_refuse_unsafe_payment_config():
    base = {"app_env": "prod", "jwt_secret": "x" * 40, "byok_encryption_key": "k"}
    base |= {"cookie_secure": True, "mock_provider_enabled": False}
    with pytest.raises(ValidationError):
        Settings(**base, payments_provider="fake", public_base_url="https://a.example")
    with pytest.raises(ValidationError):
        Settings(**base, payments_provider="inpay", public_base_url="https://a.example")
    with pytest.raises(ValidationError):
        Settings(
            **base,
            payments_provider="inpay",
            inpay_merchant_id="m",
            inpay_merchant_token=SECRET,
            public_base_url="http://a.example",
        )
    with pytest.raises(ValidationError):
        Settings(credit_packs=[{"id": "a", "credits": 1, "amount_uzs": 500}])
    with pytest.raises(ValidationError):
        Settings(
            credit_packs=[
                {"id": "a", "credits": 1, "amount_uzs": 1000},
                {"id": "a", "credits": 2, "amount_uzs": 2000},
            ]
        )
    ok = Settings(
        **base,
        payments_provider="inpay",
        inpay_merchant_id="m",
        inpay_merchant_token=SECRET,
        public_base_url="https://a.example",
    )
    assert SECRET not in repr(ok)


def test_parse_amount():
    assert parse_amount(15000) == 15000
    assert parse_amount("15000.00") == 15000
    assert parse_amount("15000.5") is None
    assert parse_amount("abc") is None
    assert parse_amount(True) is None
    assert parse_amount(None) is None


# --- inPAY adapter (httpx MockTransport) -------------------------------------------------------


class InpayMock:
    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.auth_calls = 0
        self.expire_next = False
        self.tx: object = {"success": True, "status": "success", "amount": 15000}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        path = request.url.path
        assert "/cardsystem/" not in path
        if path.endswith("/authorization/"):
            self.auth_calls += 1
            assert request.url.params["merchant_token"] == SECRET
            return httpx.Response(
                200, json={"success": True, "bearer_token": f"bearer-{self.auth_calls}"}
            )
        if self.expire_next:
            self.expire_next = False
            return httpx.Response(401, json={"detail": "expired"})
        assert request.headers["Authorization"] == f"Bearer bearer-{self.auth_calls}"
        if path.endswith("/create/"):
            return httpx.Response(
                200,
                json={"success": True, "order_id": "inp-1", "pay_url": "https://inpay.uz/pay/x"},
            )
        if path.endswith("/transactions/"):
            assert request.url.params["order_id"] == "inp-1"
            return httpx.Response(200, json=self.tx)
        return httpx.Response(404)


def _gw(mock, clock=None) -> InpayGateway:
    kwargs = {"clock": clock} if clock else {}
    return InpayGateway(
        "m-1",
        SECRET,
        "https://inpay.uz/api/v1",
        "https://aurevid.test",
        transport=httpx.MockTransport(mock),
        **kwargs,
    )


async def test_inpay_create_caches_token_and_sends_callback_urls():
    mock = InpayMock()
    gw = _gw(mock)
    assert await gw.create_order(15000, "Aurevid: 100 credits", "ord1") == (
        "inp-1",
        "https://inpay.uz/pay/x",
    )
    await gw.check("inp-1")
    await gw.check("inp-1")
    assert mock.auth_calls == 1
    import json

    body = json.loads(mock.calls[1].content)
    assert body["amount"] == 15000 and body["merchant_id"] == "m-1"
    assert body["callback_url"] == "https://aurevid.test/api/payments/inpay/callback"
    assert body["return_url"] == "https://aurevid.test/credits?order=ord1"
    assert SECRET not in repr(gw)


async def test_inpay_token_expires_after_23h():
    now = [1000.0]
    mock = InpayMock()
    gw = _gw(mock, clock=lambda: now[0])
    await gw.check("inp-1")
    now[0] += 22 * 3600
    await gw.check("inp-1")
    assert mock.auth_calls == 1
    now[0] += 2 * 3600
    await gw.check("inp-1")
    assert mock.auth_calls == 2


async def test_inpay_refreshes_once_on_401():
    mock = InpayMock()
    gw = _gw(mock)
    await gw.check("inp-1")
    mock.expire_next = True
    result = await gw.check("inp-1")
    assert result.status == "success" and mock.auth_calls == 2


async def test_inpay_persistent_401_raises_without_secret():
    def always_401(request):
        if request.url.path.endswith("/authorization/"):
            return httpx.Response(200, json={"success": True, "bearer_token": "b"})
        return httpx.Response(401, text=f"bad token {SECRET}")

    gw = InpayGateway(
        "m-1", SECRET, "https://inpay.uz/api/v1", "https://a.test", httpx.MockTransport(always_401)
    )
    with pytest.raises(GatewayError) as exc:
        await gw.check("inp-1")
    assert SECRET not in str(exc.value)


@pytest.mark.parametrize(
    ("tx", "expected"),
    [
        ({"success": True, "status": "success", "amount": 15000}, ("success", 15000)),
        ({"success": True, "data": {"status": "SUCCESS", "amount": "15000.00"}}, ("success", 15000)),
        ({"success": True, "data": [{"order_id": "inp-1", "status": "failed", "amount": 15000}]}, ("failed", 15000)),
        ({"success": True, "data": {"status": "canceled"}}, ("canceled", None)),
        ({"success": False, "status": "success", "amount": 15000}, ("pending", None)),
        ({"success": True, "order_id": "other", "status": "success", "amount": 15000}, ("pending", None)),
        ({"success": True, "status": "weird-new-state", "amount": 15000}, ("pending", 15000)),
        ([], ("pending", None)),
    ],
)  # fmt: skip
async def test_inpay_check_parses_defensively(tx, expected):
    mock = InpayMock()
    mock.tx = tx
    result = await _gw(mock).check("inp-1")
    assert (result.status, result.amount_uzs) == expected


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500, text=f"boom {SECRET}"),
        lambda r: httpx.Response(200, text=f"<html>{SECRET}</html>"),
        lambda r: httpx.Response(200, json={"success": False, "message": SECRET}),
    ],
)
async def test_inpay_auth_errors_never_contain_token(handler):
    gw = InpayGateway(
        "m-1", SECRET, "https://inpay.uz/api/v1", "https://a.test", httpx.MockTransport(handler)
    )
    with pytest.raises(GatewayError) as exc:
        await gw.create_order(15000, "x", "o")
    assert SECRET not in str(exc.value) and exc.value.__cause__ is None


async def test_inpay_network_error_hides_url_with_token():
    def boom(request):
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    gw = InpayGateway(
        "m-1", SECRET, "https://inpay.uz/api/v1", "https://a.test", httpx.MockTransport(boom)
    )
    with pytest.raises(GatewayError) as exc:
        await gw.check("inp-1")
    assert SECRET not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__


async def test_inpay_rejects_non_https_pay_url_and_low_amount():
    def handler(request):
        if request.url.path.endswith("/authorization/"):
            return httpx.Response(200, json={"success": True, "bearer_token": "b"})
        return httpx.Response(
            200, json={"success": True, "order_id": "1", "pay_url": "javascript:alert(1)"}
        )

    gw = InpayGateway(
        "m-1", SECRET, "https://inpay.uz/api/v1", "https://a.test", httpx.MockTransport(handler)
    )
    with pytest.raises(GatewayError):
        await gw.create_order(15000, "x", "o")
    with pytest.raises(GatewayError):
        await gw.create_order(999, "x", "o")


async def test_inpay_token_not_logged(caplog):
    caplog.set_level(logging.DEBUG)
    mock = InpayMock()
    await _gw(mock).create_order(15000, "x", "o")
    assert SECRET not in caplog.text


async def test_callback_path_is_the_only_csrf_exemption(anon):
    from app.main import CSRF_EXEMPT_PATHS

    assert CSRF_EXEMPT_PATHS == {CALLBACK}
    r = await anon.post(CALLBACK + "/x", json={})
    assert r.status_code == 403  # a sibling path is not exempt
