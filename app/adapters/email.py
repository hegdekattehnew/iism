import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("iism.email")


class EmailAdapter(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailAdapter(EmailAdapter):
    # Logs instead of sending; swap for SES/SendGrid/etc. via get_email_adapter().
    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("EMAIL to=%s subject=%r\n%s", to, subject, body)


def get_email_adapter() -> EmailAdapter:
    return ConsoleEmailAdapter()
