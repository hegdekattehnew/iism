"""Withdrawing consent without deleting the account, and confirming it again (Sprint 72, ADR-082).

DPDP Act 2023 s.6(4): a person may withdraw consent at any time, as easily as they gave it. The
notice used to say withdrawing *was* deleting the account, which is a different and much larger act.
A person who withdraws here is **paused**: they stay signed up, and the product stops processing
them for the things they did not strictly ask for in the moment -- employer pools and alert sweeps
(`matching/retrieval.py`), applying and registering interest (`require_not_paused`), tracking
(`analytics.record`) and push. They can still sign in, export, correct, delete, and restore.

**This is pause, not erase**, and whether that satisfies s.6(4) is a legal question the notice and
the ADR hand to counsel; deletion sits beside it for anyone who wants their data gone.

Two small functions are the whole rule, so the three guards that read it cannot disagree:

* `is_paused(user)` -- a pure read of the stamp.
* `require_not_paused(db, user)` -- the guard for a **disclosure**. It re-reads the stamp from the
  database under a shared row lock (`FOR SHARE`) rather than trusting the loaded `User`. Without it
  a withdrawal landing between an apply's check and its commit leaves a live application whose
  contact is shown to an employer after consent was withdrawn. The shared lock lives until the
  caller commits, so the withdrawal's `UPDATE` of the stamp waits for an apply in flight, and an
  apply that starts after that `UPDATE` waits for it to commit and then sees the stamp. **The
  withdrawal takes no explicit lock of its own**: a first version took `FOR UPDATE` on the read,
  and a mutation check showed it changed nothing, because the `UPDATE` conflicts with the shared
  lock all the same (a guard no test can fail only gives the next reader something to wonder about).
"""

from datetime import UTC, datetime

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity.models import User
from api.modules.identity.service import record_consent, require_current_consent

log = structlog.get_logger("iism.consent")

PAUSED_DETAIL = (
    "You have withdrawn consent, so this is switched off. Confirm the privacy notice again from "
    "your Account page to use it."
)


def is_paused(user: User) -> bool:
    return user.consent_withdrawn_at is not None


async def require_not_paused(db: AsyncSession, user: User) -> None:
    """409 `consent_withdrawn` when the person has withdrawn consent. For a disclosure only."""
    stamp = await db.scalar(
        select(User.consent_withdrawn_at)
        .where(User.id == user.id)
        .with_for_update(read=True, of=User)
        .execution_options(populate_existing=True)
    )
    if stamp is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, PAUSED_DETAIL)


async def withdraw_consent(db: AsyncSession, user: User) -> bool:
    """Stamp the withdrawal and commit. Returns whether this call changed anything.

    Idempotent. The caller then ends the disclosures that already exist (live applications and
    interests), which is why the stamp is committed *first*: from that moment nothing new can be
    shared, so the sweep that follows cannot be outrun by an apply in flight.
    """
    stamp = await db.scalar(
        select(User.consent_withdrawn_at)
        .where(User.id == user.id)
        .execution_options(populate_existing=True)
    )
    if stamp is not None:
        return False
    user.consent_withdrawn_at = datetime.now(UTC)
    await db.commit()
    log.info("consent.withdrawn")
    return True


async def restore_consent(db: AsyncSession, user: User, version: str) -> None:
    """Confirm the notice currently in force, which also clears a withdrawal.

    The same act re-consents a person whose version went stale and restores one who withdrew: in
    both the sentence agreed to is the one in force now, and a stale `version` is refused rather
    than recorded (consent to a text nobody can identify proves nothing).
    """
    require_current_consent(version, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    was_paused = user.consent_withdrawn_at is not None
    record_consent(user, version)
    user.consent_withdrawn_at = None
    await db.commit()
    log.info("consent.confirmed", restored=was_paused)
