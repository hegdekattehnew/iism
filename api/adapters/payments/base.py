"""The payment port (ADR-017, ADR-043).

Business logic that ever needs to move money must depend on this protocol,
never on a gateway SDK -- the same rule `notifications/` and `nsqf/` already
follow. There is no caller yet: course checkout does not exist. The port is
written now so that rule holds from the first line of checkout code, rather
than being retrofitted once a gateway call already sits somewhere convenient.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PaymentProvider(Protocol):
    """Creates a payment for a fixed amount against a caller-supplied reference.

    `reference` is an idempotency key the caller controls -- an order id, once
    an `Order` table exists -- so retrying a failed request never charges
    twice. Returns the provider's own transaction id; this port stores
    nothing and defines no `Order`, `Entitlement` or `Payout` model (ADR-043).
    """

    async def create_payment(self, *, amount_paise: int, currency: str, reference: str) -> str: ...


class PaymentError(RuntimeError):
    """Payment could not be created. Callers decide whether that is fatal."""
