"""Career ladders: where could a person move to next (Sprint 42, ADR-049).

The module ADR-008 reserved as `career_paths/`, named shorter. It is a **leaf**:
it depends on skills (which roles build on one), matching (the one scorer, and the
courses that close a gap), marketplace (the profile) and analytics, and nothing
depends on it -- the shape `alerts/` and `privacy/` have, for the same reason.

It owns no table. A ladder is derived at read time from the national
qualification data and never stored, so it cannot go stale and erasure has
nothing here to remove.
"""

from api.modules.careers.routes import router

__all__ = ["router"]
