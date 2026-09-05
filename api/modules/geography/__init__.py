"""Public interface of the geography module.

Reference data only for now — no routes, because nothing consumes it through
HTTP yet. When the job and profile forms become dropdowns they get a service and
routes here, following the `api/modules/skills/` shape.
"""

from api.modules.geography.models import District, State, SubDistrict

__all__ = ["District", "State", "SubDistrict"]
