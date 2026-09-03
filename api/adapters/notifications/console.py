"""Development provider: records that a message was sent.

Deliberately the default in development so the OTP flow can be exercised end to
end with no vendor account. It refuses to run outside development -- a silent
no-op provider in production would look exactly like working authentication
while nobody could ever sign in.

**It does not log the message body.** An OTP is a live credential and a phone
number is personal data; ADR-023 forbids either reaching a log sink, and logs
outlive the code's five-minute TTL by months once shipped to an aggregator.
Developers read the code from the API response instead, which is itself gated
on Settings.expose_otp.
"""

import logging

from api.adapters.notifications.base import NotificationError
from api.core.config import get_settings

logger = logging.getLogger("iism.notifications")


def mask_phone(phone: str) -> str:
    """+919812349999 -> +9198*****999.

    Enough to correlate a support report, not enough to identify or dial.
    """
    if len(phone) < 8:
        return "*" * len(phone)
    return f"{phone[:5]}{'*' * (len(phone) - 8)}{phone[-3:]}"


class ConsoleNotificationProvider:
    async def send_sms(self, phone: str, message: str) -> None:
        if get_settings().environment == "production":
            raise NotificationError("ConsoleNotificationProvider must not be used in production")
        # Length only: confirms delivery was attempted and the body was
        # non-empty, without recording what it said.
        logger.warning("notification dispatched to %s (%d chars)", mask_phone(phone), len(message))
