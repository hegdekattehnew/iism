"""The phones a person has signed in on (Sprint 65, BL-15.6, ADR-075): the one writer of
`device_tokens`.

* **A token belongs to one person at a time.** Registering a token another account holds *moves*
  it: on a shared phone, the last person to sign in is the one the next push is for, and the one
  before must stop receiving it. One atomic upsert on the unique token, so two requests cannot
  leave it held twice.
* **Unregistering is idempotent and reveals nothing**: it answers the same whether the token was
  theirs, someone else's or unknown, and it deletes only the caller's own.
* **A person holds at most `MAX_DEVICES`**; the oldest are dropped, so a loop of registrations
  cannot grow a table of one person's phones for ever.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.notifications.models import DeviceToken

MAX_DEVICES = 10


async def register(
    db: AsyncSession, user_id: uuid.UUID, *, token: str, platform: str, locale: str
) -> None:
    """Record this phone for this person. Commits."""
    # `clock_timestamp()`, not `now()`: `now()` is the transaction's start, which would make two
    # registrations in one transaction (and a test) tie, and "the newest stay" mean nothing.
    stmt = insert(DeviceToken).values(
        user_id=user_id,
        token=token,
        platform=platform,
        locale=locale,
        created_at=func.clock_timestamp(),
        last_seen_at=func.clock_timestamp(),
    )
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=[DeviceToken.token],
            set_={
                "user_id": user_id,
                "platform": platform,
                "locale": locale,
                "last_seen_at": func.clock_timestamp(),
            },
        )
    )
    # Keep the newest MAX_DEVICES; the rest are phones this person stopped using.
    keep = (
        select(DeviceToken.id)
        .where(DeviceToken.user_id == user_id)
        .order_by(DeviceToken.last_seen_at.desc(), DeviceToken.id)
        .limit(MAX_DEVICES)
    )
    await db.execute(
        delete(DeviceToken).where(DeviceToken.user_id == user_id, DeviceToken.id.not_in(keep))
    )
    await db.commit()


async def unregister(db: AsyncSession, user_id: uuid.UUID, token: str) -> None:
    """Forget this phone for this person. Only their own row is touched. Commits."""
    await db.execute(
        delete(DeviceToken).where(DeviceToken.user_id == user_id, DeviceToken.token == token)
    )
    await db.commit()
