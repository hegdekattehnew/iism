"""A push provider that writes to the log instead of a phone.

It exists so the whole path (a device registers, a notice queues a push, the drain sends it, a dead
token is removed) runs and is tested without a vendor account. **It refuses production**, like
`ConsoleNotificationProvider`: a missing push vendor must fail loudly rather than look like
delivery that nobody receives.
"""

import hashlib
from collections.abc import Mapping

import structlog

from api.core.config import get_settings

log = structlog.get_logger("iism.push")


class ConsolePushProvider:
    async def send_push(self, token: str, title: str, body: str, data: Mapping[str, str]) -> None:
        if not get_settings().is_local:
            raise RuntimeError(
                "No push provider is configured for this environment. Implement a real "
                "PushProvider (ADR-075) and select it in api/adapters/push/__init__.py."
            )
        # A digest, never the token: a token is the credential for sending to that phone.
        digest = hashlib.sha256(token.encode()).hexdigest()[:10]
        log.info("push.console", device=digest, title=title, body=body, data=dict(data))
