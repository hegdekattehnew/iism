"""Geography over the wire. Reference data, so read-only and permissive."""

import uuid

from pydantic import BaseModel, ConfigDict


class StateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    state_code: int | None = None
    name: str


class DistrictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    district_code: int | None = None
    name: str | None = None
    state_id: uuid.UUID | None = None
