"""Push adapters. Import a factory, not an implementation."""

from functools import lru_cache

from api.adapters.push.base import InvalidDeviceToken, PushProvider
from api.adapters.push.console import ConsolePushProvider


@lru_cache
def get_push_provider() -> PushProvider:
    """Chosen by configuration. A real provider (Expo Push, FCM, APNs) slots in here behind the
    same protocol once the owner has the credentials (ADR-075)."""
    return ConsolePushProvider()


__all__ = ["ConsolePushProvider", "InvalidDeviceToken", "PushProvider", "get_push_provider"]
