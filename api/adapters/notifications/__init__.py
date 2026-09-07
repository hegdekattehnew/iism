"""Notification adapters. Import a factory, not an implementation."""

from functools import lru_cache

from api.adapters.notifications.base import (
    EmailProvider,
    NotificationError,
    NotificationProvider,
)
from api.adapters.notifications.console import ConsoleNotificationProvider
from api.adapters.notifications.console_email import ConsoleEmailProvider


@lru_cache
def get_notification_provider() -> NotificationProvider:
    """Chosen by configuration. Real providers (MSG91, Gupshup) slot in here
    behind the same protocol; ADR-032 also requires a failover provider once
    SMS is on the login critical path for real users."""
    return ConsoleNotificationProvider()


@lru_cache
def get_email_provider() -> EmailProvider:
    """Chosen by configuration, like its SMS sibling. Organisation sign-in puts
    email on the login critical path (ADR-038), so this needs a real provider
    before any organisation outside development can sign in."""
    return ConsoleEmailProvider()


__all__ = [
    "ConsoleEmailProvider",
    "ConsoleNotificationProvider",
    "EmailProvider",
    "NotificationError",
    "NotificationProvider",
    "get_email_provider",
    "get_notification_provider",
]
