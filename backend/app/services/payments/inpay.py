# SPDX-License-Identifier: AGPL-3.0-or-later
"""inPAY.uz adapter (Payme, Click, Uzcard, Humo via hosted checkout).

Flow: GET /authorization/ -> bearer token (cached ~23 h, refreshed once on 401);
POST /create/ -> (order_id, pay_url); GET /transactions/ -> real status + amount.
Hosted checkout only: the /cardsystem/* API is never used, card data never reaches us.

Secrets: the merchant token is sent only to INPAY_BASE_URL. Errors raised here never contain
the token, request URLs or response bodies, and httpx request logging is muted because it would
print the authorization URL (which carries the token as a query parameter).
"""

import asyncio
import logging
import time
from urllib.parse import urlsplit

import httpx

from app.services.payments.base import (
    CheckResult,
    GatewayError,
    normalise_status,
    parse_amount,
)

# httpx logs full request URLs at INFO; the authorization URL contains the merchant token.
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN_TTL_SECONDS = 23 * 3600
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _payload(data: object) -> dict:
    """Responses may be flat or nested under "data" (dict or list)."""
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict):
            return {**data, **inner}
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return {**data, **inner[0]}
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return {}


def _pick_txn(data: object, provider_order_id: str) -> dict:
    """Pick the entry for our order when the response is a list of transactions."""
    items = None
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        items = data["data"]
    elif isinstance(data, list):
        items = data
    if items:
        for item in items:
            if isinstance(item, dict) and str(item.get("order_id", "")) == provider_order_id:
                return item
    return _payload(data)


class InpayGateway:
    name = "inpay"

    def __init__(
        self,
        merchant_id: str,
        merchant_token: str,
        base_url: str,
        public_base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        clock=time.monotonic,
    ) -> None:
        if not merchant_id or not merchant_token:
            raise GatewayError("inpay merchant credentials are not configured")
        self._merchant_id = merchant_id
        self._merchant_token = merchant_token
        self._base = base_url.rstrip("/")
        self._public = public_base_url.rstrip("/")
        self._transport = transport
        self._clock = clock
        self._token: str | None = None
        self._token_expires = 0.0
        self._lock = asyncio.Lock()

    def __repr__(self) -> str:  # never show credentials
        return f"InpayGateway(base={self._base!r})"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=TIMEOUT, transport=self._transport, follow_redirects=False)

    async def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            async with self._client() as client:
                return await client.request(method, f"{self._base}{path}", **kwargs)
        except httpx.HTTPError as exc:
            # The exception text can include the request URL: report only the type.
            raise GatewayError(f"inpay network error ({type(exc).__name__})") from None

    @staticmethod
    def _json(res: httpx.Response, what: str) -> object:
        try:
            return res.json()
        except ValueError:
            raise GatewayError(f"inpay {what}: invalid JSON (HTTP {res.status_code})") from None

    async def _bearer(self, force: bool = False) -> str:
        async with self._lock:
            if not force and self._token and self._clock() < self._token_expires:
                return self._token
            res = await self._send(
                "GET",
                "/authorization/",
                params={"merchant_id": self._merchant_id, "merchant_token": self._merchant_token},
            )
            if res.status_code != 200:
                raise GatewayError(f"inpay authorization failed (HTTP {res.status_code})")
            data = _payload(self._json(res, "authorization"))
            token = data.get("bearer_token") or data.get("token")
            if data.get("success") is False or not isinstance(token, str) or not token:
                raise GatewayError("inpay authorization refused")
            self._token, self._token_expires = token, self._clock() + TOKEN_TTL_SECONDS
            return token

    async def _authed(self, method: str, path: str, what: str, **kwargs) -> object:
        token = await self._bearer()
        for attempt in range(2):
            res = await self._send(
                method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs
            )
            if res.status_code == 401 and attempt == 0:
                token = await self._bearer(force=True)
                continue
            if res.status_code != 200:
                raise GatewayError(f"inpay {what} failed (HTTP {res.status_code})")
            return self._json(res, what)
        raise GatewayError(f"inpay {what}: unauthorized after token refresh")

    async def create_order(
        self, amount_uzs: int, description: str, order_ref: str
    ) -> tuple[str, str]:
        if amount_uzs < 1000:
            raise GatewayError("amount below gateway minimum")
        body = {
            "merchant_id": self._merchant_id,
            "token": self._merchant_token,
            "amount": amount_uzs,
            "description": description,
            "callback_url": f"{self._public}/api/payments/inpay/callback",
            "return_url": f"{self._public}/credits?order={order_ref}",
        }
        data = _payload(await self._authed("POST", "/create/", "create", json=body))
        order_id, pay_url = data.get("order_id"), data.get("pay_url")
        if data.get("success") is False or not order_id or not isinstance(pay_url, str):
            raise GatewayError("inpay create: order refused")
        parts = urlsplit(pay_url)
        if parts.scheme != "https" or not parts.netloc:
            raise GatewayError("inpay create: pay_url is not https")
        return str(order_id)[:64], pay_url[:1024]

    async def check(self, provider_order_id: str) -> CheckResult:
        data = await self._authed(
            "GET",
            "/transactions/",
            "transactions",
            params={"order_id": provider_order_id, "merchant_id": self._merchant_id},
        )
        txn = _pick_txn(data, provider_order_id)
        if not txn or txn.get("success") is False:
            return CheckResult("pending", None, None)
        returned_id = txn.get("order_id")
        if returned_id is not None and str(returned_id) != provider_order_id:
            return CheckResult("pending", None, None)  # answer about another order: ignore
        txn_id = txn.get("transaction_id") or txn.get("id")
        return CheckResult(
            normalise_status(txn.get("status")),
            parse_amount(txn.get("amount")),
            str(txn_id)[:64] if txn_id not in (None, "") else None,
        )
