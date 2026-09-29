"""Payment adapters (ADR-043). Import a factory, not an implementation.

There is no real provider and no route or service in the tree calls
`get_payment_provider` yet -- see the ADR for why the port exists before its
first caller.
"""

from functools import lru_cache

from api.adapters.payments.base import PaymentError, PaymentProvider
from api.adapters.payments.console import ConsolePaymentProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    """Chosen by configuration, once there is a configuration to choose from.
    A real gateway (Razorpay, Cashfree) slots in here behind the same
    protocol, the day course checkout is built."""
    return ConsolePaymentProvider()


__all__ = [
    "ConsolePaymentProvider",
    "PaymentError",
    "PaymentProvider",
    "get_payment_provider",
]
