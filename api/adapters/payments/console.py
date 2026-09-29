"""Development provider: refuses to run at all, in every environment.

Unlike its `notifications/` and `email/` siblings, this has no legitimate
success path to fall back to in development -- there is no course-checkout
feature calling it yet (ADR-043), so returning a fabricated transaction id
would fabricate a transaction for a flow that does not exist. It refuses
unconditionally rather than only in production.

The production check stays anyway, in the same shape as its siblings, so the
day a real provider replaces this one, the line that must never be deleted
is already the one being overwritten -- not a new rule introduced at the same
moment the stakes go up.
"""

import logging

from api.adapters.payments.base import PaymentError
from api.core.config import get_settings

__all__ = ["ConsolePaymentProvider"]

logger = logging.getLogger("iism.payments")


class ConsolePaymentProvider:
    async def create_payment(self, *, amount_paise: int, currency: str, reference: str) -> str:
        if get_settings().environment == "production":
            raise PaymentError("ConsolePaymentProvider must not be used in production")
        logger.warning("payment refused: no provider configured (reference=%s)", reference)
        raise PaymentError(
            "No payment provider is configured -- course checkout does not exist yet (ADR-043); "
            "this port has no feature calling it to succeed for."
        )
