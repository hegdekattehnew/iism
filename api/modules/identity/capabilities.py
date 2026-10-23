"""What a training organisation does: sells courses, delivers training, or both (ADR-102).

Two booleans on one organisation, never two tenants for one real organisation (ADR-038). This is the
only writer of `Tenant.publishes_courses` and `Tenant.delivers_training` after creation, and it
holds the rules about changing them:

- **Owner only, and still an owner when it counts.** A standing change to what the organisation is:
  the route asks for `ORG_UPDATE`, and `_require_owner_now` asks again once the lock is held,
  because another owner may have demoted this one since the request arrived (ADR-051).
- **Always at least one.** An organisation that neither sells nor delivers can do nothing.
- **Never from under live work.** Turning off *sells courses* is refused while the organisation has
  published courses (they would be live and unmanageable); turning off *delivers training* is
  refused while it has anything that delivery means: open centres (Sprint 95) today, batches
  (Sprint 98) later, each added to `delivery_in_progress`.
- **Recorded.** One `organisation_capability_changed` event per capability that changed, after
  the commit and subjected to the organisation (`record()` commits).
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity.invitations import (
    _lock_ownership,
    _record_for_tenant,
    _require_owner_now,
)
from api.modules.identity.models import Tenant, User


async def _published_courses(db: AsyncSession, tenant: Tenant) -> int:
    # Function-level import: `marketplace` imports `identity`, so a module-level one is a cycle.
    from api.modules.marketplace.models import Course

    return (
        await db.scalar(
            select(func.count())
            .select_from(Course)
            .where(Course.tenant_id == tenant.id, Course.status == "published")
        )
    ) or 0


async def _live_arrangements(db: AsyncSession, tenant: Tenant, side: str) -> int:
    """Delivery arrangements with other organisations that are still open (asked or approved).

    Imported inside the function: `delivery` depends on this package for `Tenant`, so a module-level
    import is the cycle `marketplace` is read through the same way for `_published_courses`.
    """
    from api.modules.delivery.models import CourseDeliveryAuthorisation as Arrangement

    column = Arrangement.provider_id if side == "provider" else Arrangement.partner_id
    return (
        await db.scalar(
            select(func.count())
            .select_from(Arrangement)
            .where(column == tenant.id, Arrangement.ended_at.is_(None))
        )
    ) or 0


async def delivery_in_progress(db: AsyncSession, tenant: Tenant) -> str | None:
    """Why this organisation cannot stop delivering training, or `None` if it can.

    Active centres (Sprint 95) keep it delivering; batches (Sprint 98) add their own reason here:
    the rule is written once so the guard cannot be forgotten when they land. A closed centre is
    history and holds nothing.
    """
    active = (
        await db.scalar(
            select(func.count())
            .select_from(Tenant)
            .where(
                Tenant.parent_id == tenant.id,
                Tenant.tenant_type == "training_centre",
                Tenant.closed_at.is_(None),
            )
        )
    ) or 0
    if active:
        return "This organisation has centres that are open. Close them first"
    # An arrangement to deliver somebody else's course (Sprint 97) is a standing promise, asked or
    # approved: ending it is the organisation's own act, not a side effect of a switch.
    if await _live_arrangements(db, tenant, "partner"):
        return (
            "This organisation has arrangements to deliver other organisations' courses. "
            "Decline or end them first"
        )
    return None


async def set_capabilities(
    db: AsyncSession,
    *,
    tenant: Tenant,
    actor: User,
    sells_courses: bool | None = None,
    delivers_training: bool | None = None,
) -> Tenant:
    """Change what an organisation does, and commit. An absent argument leaves that one alone."""
    if tenant.tenant_type != "course_provider":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only a training organisation sells courses or delivers training",
        )
    await _lock_ownership(db, tenant.id)
    await _require_owner_now(db, tenant.id, actor.id)
    # Read again under the lock: another owner may have changed the flags a moment ago.
    await db.refresh(tenant)

    sells = tenant.publishes_courses if sells_courses is None else sells_courses
    delivers = tenant.delivers_training if delivers_training is None else delivers_training
    if not (sells or delivers):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A training organisation sells courses, delivers training, or both",
        )
    if tenant.publishes_courses and not sells and await _published_courses(db, tenant) > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This organisation has published courses. Unpublish them first",
        )
    if (
        tenant.publishes_courses
        and not sells
        and await _live_arrangements(db, tenant, "provider") > 0
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Other organisations hold arrangements to deliver this organisation's courses. "
            "Decline or end them first",
        )
    if tenant.delivers_training and not delivers:
        reason = await delivery_in_progress(db, tenant)
        if reason is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, reason)

    changed: list[tuple[str, bool]] = []
    if sells != tenant.publishes_courses:
        tenant.publishes_courses = sells
        changed.append(("sells_courses", sells))
    if delivers != tenant.delivers_training:
        tenant.delivers_training = delivers
        changed.append(("delivers_training", delivers))
    await db.commit()
    await db.refresh(tenant)
    # After the commit, never inside it: `record()` commits (see `_record_for_tenant`).
    for capability, enabled in changed:
        await _record_for_tenant(
            db,
            "organisation_capability_changed",
            tenant_id=tenant.id,
            actor_user_id=actor.id,
            payload={"capability": capability, "enabled": enabled},
        )
    return tenant
