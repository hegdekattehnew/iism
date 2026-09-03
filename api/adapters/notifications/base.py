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


class NotificationError(RuntimeError):
    """Delivery failed. Callers decide whether that is fatal.

    For OTP it is: the user cannot proceed without the code, so a silent failure
    would present as a broken login rather than a delivery problem.
    """
