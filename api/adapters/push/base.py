"""The push port (ADR-017, ADR-075).

Business logic depends on this protocol, never on a vendor SDK: Expo Push, Firebase and APNs are
each a new implementation and one line in `get_push_provider`, with no change to the outbox.

**A push carries no free text.** The caller builds `title` and `body` from a fixed table and `data`
holds a template name and an in-app path; a provider must pass them through and add nothing.
"""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


class InvalidDeviceToken(RuntimeError):
    """The provider says this token will never work again (the app was uninstalled, the token
    rotated). The drain deletes it: sending to it again is only noise, and a dead token that is
    never removed is a row held about a person for no purpose."""


@runtime_checkable
class PushProvider(Protocol):
    async def send_push(
        self, token: str, title: str, body: str, data: Mapping[str, str]
    ) -> None: ...
