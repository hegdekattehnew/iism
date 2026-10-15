import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class DeviceIn(BaseModel):
    """A phone registering to be sent pushes. The token is opaque to us: only printable text with
    no whitespace is accepted, so what is stored can be logged as a digest and sent as-is."""

    token: str = Field(min_length=10, max_length=512)
    platform: Literal["android", "ios"]
    locale: str = Field(default="en", min_length=2, max_length=8)

    @field_validator("token")
    @classmethod
    def _printable(cls, value: str) -> str:
        if not value.isprintable() or any(ch.isspace() for ch in value):
            raise ValueError("token must be printable text with no spaces")
        return value


class DeviceRemoveIn(BaseModel):
    token: str = Field(min_length=10, max_length=512)
