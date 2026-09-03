"""Development provider: writes the message to the application log.

Deliberately the default in development so the OTP flow can be exercised end to
end with no vendor account. It refuses to run outside development — a silent
no-op provider in production would look exactly like working authentication
while nobody could ever sign in.
"""

import logging

from api.adapters.notifications.base import NotificationError
from api.core.config import get_settings

logger = logging.getLogger("iism.notifications")


class ConsoleNotificationProvider:
    async def send_sms(self, phone: str, message: str) -> None:
        if get_settings().environment == "production":
            raise NotificationError("ConsoleNotificationProvider must not be used in production")
        logger.warning("SMS to %s: %s", phone, message)
