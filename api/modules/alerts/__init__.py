"""Reaching a candidate who is not on the site.

A sibling of `notifications/` rather than part of it: the outbox knows how to
deliver a message and nothing about who should get one. This module decides
*who*, using the one scorer (ADR-037), and hands the result to that outbox.

It depends on matching, marketplace, identity and notifications. **Nothing
depends on it** -- the same shape `privacy/` has, and for the same reason:
anything that reached back into this would be coupling a request path to a
worker's schedule.
"""

from api.modules.alerts.models import JobAlert
from api.modules.alerts.service import close_expired, sweep
from api.modules.alerts.tasks import close_expired_jobs, send_job_alerts

__all__ = [
    "JobAlert",
    "close_expired",
    "close_expired_jobs",
    "send_job_alerts",
    "sweep",
]
