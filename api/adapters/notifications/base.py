"""The notification port (ADR-017).

Business logic depends on this protocol, never on a vendor SDK. Swapping MSG91
for Gupshup, or adding WhatsApp, is then a new implementation and one line of
configuration — no change to the identity module.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class NotificationProvider(Protocol):
    """Sends a transactional message to a phone number."""

    async def send_sms(self, phone: str, message: str) -> None: ...


@runtime_checkable
class EmailProvider(Protocol):
    """Sends a transactional email.

    A separate port rather than a second method on `NotificationProvider`.
    SMS and email are different vendors with different credentials, failure
    modes and compliance regimes -- in India, DLT registration applies to one
    and not the other -- so one protocol serving both would force every
    implementation to stub the half it does not do (ADR-017).
    """

    async def send_email(self, address: str, subject: str, body: str) -> None: ...


class NotificationError(RuntimeError):
    """Delivery failed. Callers decide whether that is fatal.

    For OTP it is: the user cannot proceed without the code, so a silent failure
    would present as a broken login rather than a delivery problem.
    """
