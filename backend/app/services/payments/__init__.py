# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional credit packs paid in UZS through a hosted-checkout gateway (see orders.py)."""

from app.config import get_settings
from app.services.payments.base import CheckResult, GatewayError, PaymentGateway
from app.services.payments.fake import FakeGateway
from app.services.payments.inpay import InpayGateway

__all__ = ["CheckResult", "GatewayError", "PaymentGateway", "get_gateway"]

_inpay: dict[tuple[str, str, str], InpayGateway] = {}


def get_gateway() -> PaymentGateway | None:
    """The configured gateway, or None when payments are disabled (PAYMENTS_PROVIDER=none)."""
    s = get_settings()
    if s.payments_provider == "fake":
        return FakeGateway(s.public_base_url)
    if s.payments_provider == "inpay":
        # One instance per configuration so the bearer token cache is shared.
        key = (s.inpay_base_url, s.inpay_merchant_id, s.public_base_url)
        if key not in _inpay:
            _inpay.clear()
            _inpay[key] = InpayGateway(
                s.inpay_merchant_id, s.inpay_merchant_token, s.inpay_base_url, s.public_base_url
            )
        return _inpay[key]
    return None
