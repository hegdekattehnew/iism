"""Public interface of the delivery module (Sprint 97, ADR-102, ADR-103).

Who may deliver whose courses: a leaf that depends on identity (organisations), marketplace's models
(the course an arrangement names), notifications and analytics. Batches (Sprint 98) ask it
`authorises`; nothing else depends on it, and identity reads its table only inside a function (the
capability guards), the way it reads courses.
"""

from api.modules.delivery.models import CourseDeliveryAuthorisation
from api.modules.delivery.routes import public_router, router
from api.modules.delivery.service import authorises, on_ended

__all__ = ["CourseDeliveryAuthorisation", "authorises", "on_ended", "public_router", "router"]
