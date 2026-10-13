"""Public interface of the grievances module (Sprint 57, BL-14.3, ADR-067).

Sending us a message (a question, a complaint, a request about your data), the operator's queue
that answers it, and the retention that forgets it. A leaf, the `assessment/` and `interests/`
shape: depends on `identity` (the user) and `notifications` (a notice on each change); nothing
depends on it except `privacy/`, which exports and erases a person's own messages.
"""

from api.modules.grievances.models import Grievance
from api.modules.grievances.routes import me_router, ops_router, router
from api.modules.grievances.service import erase_for_user, export_for_user, purge_expired
from api.modules.grievances.tasks import purge_expired_grievances

__all__ = [
    "Grievance",
    "erase_for_user",
    "export_for_user",
    "me_router",
    "ops_router",
    "purge_expired",
    "purge_expired_grievances",
    "router",
]
