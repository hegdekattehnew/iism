"""Public interface of the analytics module (ADR-025)."""

from api.modules.analytics.models import EVENT_NAMES, AnalyticsEvent
from api.modules.analytics.routes import router
from api.modules.analytics.service import record

__all__ = ["EVENT_NAMES", "AnalyticsEvent", "record", "router"]
