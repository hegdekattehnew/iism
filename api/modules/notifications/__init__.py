"""Telling someone that something happened.

Sprint 21 closed the loop and told nobody: an application arrived, and the
employer found out only by opening a page they had no reason to open. This
module is the queue that fixes that.

It depends on identity (to resolve an address) and on the notification
adapters (ADR-017); applications depends on it. Nothing here knows what an
application *is* -- it is handed a template name and a payload.
"""

from api.modules.notifications.models import Notification
from api.modules.notifications.routes import router
from api.modules.notifications.service import drain, enqueue

__all__ = ["Notification", "drain", "enqueue", "router"]
