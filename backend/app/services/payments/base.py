# SPDX-License-Identifier: AGPL-3.0-or-later
"""Payment gateway interface.

Gateways only use hosted checkout: the user pays on the gateway's page, card data never touches
our server. A gateway answers two questions: "create an order" and "what is the real state of
this order". Webhooks are only a trigger to ask the second question.
"""

from decimal import Decimal, InvalidOperation
from typing import Literal, NamedTuple, Protocol

CheckStatus = Literal["success", "pending", "failed", "canceled"]


class GatewayError(Exception):
    """Safe to log: messages never contain credentials, URLs with secrets or upstream bodies."""


class CheckResult(NamedTuple):
    status: CheckStatus
    amount_uzs: int | None  # None when missing or not a whole number of so'm
    txn_id: str | None


class PaymentGateway(Protocol):
    name: str

    async def create_order(
        self, amount_uzs: int, description: str, order_ref: str
    ) -> tuple[str, str]:
        """Returns (provider_order_id, pay_url). `order_ref` is our own order id."""
        ...

    async def check(self, provider_order_id: str) -> CheckResult: ...


def parse_amount(value: object) -> int | None:
    """15000, "15000", "15000.00" -> 15000; anything else (fractions, junk, bool) -> None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite() or d != d.to_integral_value():
        return None
    return int(d)


def normalise_status(value: object) -> CheckStatus:
    s = str(value or "").strip().lower()
    if s in {"success", "succeeded", "paid", "completed"}:
        return "success"
    if s in {"failed", "fail", "error", "rejected", "declined"}:
        return "failed"
    if s in {"canceled", "cancelled", "cancel", "expired"}:
        return "canceled"
    return "pending"  # unknown states are re-checked later, never credited
