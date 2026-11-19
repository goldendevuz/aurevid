# SPDX-License-Identifier: AGPL-3.0-or-later
"""In-memory fake gateway for development and tests (refused when APP_ENV=prod).

Orders live only in this process. With `autopay` on (the default, handy in dev) an order is
reported as paid on its first check; tests switch it off and call `settle()` themselves.
"""

import secrets

from app.services.payments.base import CheckResult, CheckStatus, GatewayError

_orders: dict[str, dict] = {}
autopay = True


def reset() -> None:
    _orders.clear()


def settle(provider_order_id: str, status: CheckStatus = "success", amount: int | None = None):
    order = _orders[provider_order_id]
    order["status"] = status
    if amount is not None:
        order["amount"] = amount
    if status == "success":
        order["txn"] = "fake_txn_" + secrets.token_hex(6)


class FakeGateway:
    name = "fake"

    def __init__(self, public_base_url: str = "") -> None:
        self.public_base_url = public_base_url.rstrip("/")

    async def create_order(
        self, amount_uzs: int, description: str, order_ref: str
    ) -> tuple[str, str]:
        if amount_uzs < 1000:
            raise GatewayError("amount below gateway minimum")
        pid = "fake_" + secrets.token_hex(8)
        _orders[pid] = {"amount": amount_uzs, "status": "pending", "txn": None}
        # No real checkout: send the user straight back to the return page.
        return pid, f"{self.public_base_url}/credits?order={order_ref}"

    async def check(self, provider_order_id: str) -> CheckResult:
        order = _orders.get(provider_order_id)
        if order is None:
            return CheckResult("pending", None, None)
        if autopay and order["status"] == "pending":
            settle(provider_order_id)
        return CheckResult(order["status"], order["amount"], order["txn"])
