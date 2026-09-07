"""Development email provider: records that a message was sent.

Deliberately indistinguishable in shape from `ConsoleNotificationProvider`,
including the part that matters most: **it refuses to run in production.** A
silent no-op here would look exactly like working organisation sign-in while
nobody could ever receive a code.

**It logs neither the body nor the full address.** A one-time code is a live
credential and an email address is personal data (ADR-023). An address is also
the identifier an enumeration attack wants, so the log carries only enough to
correlate a support report.
"""

import logging

from api.adapters.notifications.base import NotificationError
from api.core.config import get_settings

logger = logging.getLogger("iism.notifications")


def mask_email(address: str) -> str:
    """`priya.sharma@example.com` -> `pr****@example.com`.

    The domain survives because it is what a support conversation needs; the
    local part does not, because that is the half that identifies a person.
    """
    local, _, domain = address.partition("@")
    if not domain:
        return "*" * len(address)
    keep = local[:2] if len(local) > 3 else ""
    return f"{keep}{'*' * max(len(local) - len(keep), 1)}@{domain}"


class ConsoleEmailProvider:
    async def send_email(self, address: str, subject: str, body: str) -> None:
        if get_settings().environment == "production":
            raise NotificationError("ConsoleEmailProvider must not be used in production")
        # Subject length, not the subject: even a subject line can carry the
        # thing it is announcing.
        logger.warning(
            "email dispatched to %s (subject %d chars, body %d chars)",
            mask_email(address),
            len(subject),
            len(body),
        )
