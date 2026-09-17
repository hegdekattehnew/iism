import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    """An in-app notice. The words are rendered by the client from `template`
    and `payload`, so they follow the language the reader is browsing in rather
    than the one they were queued in."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template: str
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None = None
