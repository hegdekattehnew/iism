"""Notification adapters. Import the factory, not an implementation."""

from functools import lru_cache

from api.adapters.notifications.base import NotificationError, NotificationProvider
from api.adapters.notifications.console import ConsoleNotificationProvider


@lru_cache
def get_notification_provider() -> NotificationProvider:
    """Chosen by configuration. Real providers (MSG91, Gupshup) slot in here
    behind the same protocol; ADR-032 also requires a failover provider once
    SMS is on the login critical path for real users."""
    return ConsoleNotificationProvider()


__all__ = [
    "ConsoleNotificationProvider",
    "NotificationError",
    "NotificationProvider",
    "get_notification_provider",
]
