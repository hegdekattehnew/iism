"""Public interface of the geography module.

Its own module rather than part of `skills`, because jobs and candidate
profiles reference it and neither is a skill. Now carries a service and routes:
job publishing has to resolve a written place name to the master **on write**,
or the listing is invisible to location-filtered matching.
"""

from api.modules.geography.models import District, State, SubDistrict
from api.modules.geography.routes import router
from api.modules.geography.service import ResolvedLocation, resolve_location

__all__ = [
    "District",
    "ResolvedLocation",
    "State",
    "SubDistrict",
    "resolve_location",
    "router",
]
