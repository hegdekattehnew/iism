"""Export and erasure.

Deletes are issued explicitly, table by table, rather than trusting database
cascades. Some foreign keys cascade and some only cascade in the ORM, and
"everything went" is the one claim an erasure path must never make on
assumption. The analytics link is cleared rather than the events deleted: the
events carry no name, phone or email, so with the account gone they identify
nobody, and they keep the aggregate counts honest.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.config import get_settings
from api.core.security import revoke_all_for_user
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import Membership, Tenant, User
from api.modules.marketplace.models import (
    CandidateProfile,
    CandidateSkill,
    Course,
    CourseSkill,
    Job,
    JobSkill,
)
from api.modules.marketplace.schemas import CandidateProfileFull
from api.modules.privacy.schemas import DeletionPreview, OrganisationFate

log = structlog.get_logger("iism.privacy")


async def _memberships(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Membership, Tenant]]:
    rows = await db.execute(
        select(Membership, Tenant)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == user_id)
    )
    return [(m, t) for m, t in rows.all()]


async def _listings(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    jobs = await db.scalar(select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id))
    courses = await db.scalar(
        select(func.count()).select_from(Course).where(Course.tenant_id == tenant_id)
    )
    return (jobs or 0) + (courses or 0)


async def deletion_preview(db: AsyncSession, user: User) -> DeletionPreview:
    deleted: list[OrganisationFate] = []
    blocked: list[OrganisationFate] = []
    for membership, tenant in await _memberships(db, user.id):
        if tenant.tenant_type == "personal":
            continue
        others = await db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.tenant_id == tenant.id, Membership.user_id != user.id)
        )
        fate = OrganisationFate(
            slug=tenant.slug, name=tenant.name, listings=await _listings(db, tenant.id)
        )
        if not others:
            deleted.append(fate)
        elif membership.role == "owner":
            other_owners = await db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.tenant_id == tenant.id,
                    Membership.user_id != user.id,
                    Membership.role == "owner",
                )
            )
            if not other_owners:
                blocked.append(fate)
    return DeletionPreview(organisations_deleted=deleted, blocked_by=blocked)


async def _delete_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    job_ids = select(Job.id).where(Job.tenant_id == tenant_id)
    course_ids = select(Course.id).where(Course.tenant_id == tenant_id)
    await db.execute(delete(JobSkill).where(JobSkill.job_id.in_(job_ids)))
    await db.execute(delete(Job).where(Job.tenant_id == tenant_id))
    await db.execute(delete(CourseSkill).where(CourseSkill.course_id.in_(course_ids)))
    await db.execute(delete(Course).where(Course.tenant_id == tenant_id))
    await db.execute(delete(Membership).where(Membership.tenant_id == tenant_id))
    await db.execute(delete(Tenant).where(Tenant.id == tenant_id))


async def delete_account(db: AsyncSession, user: User) -> DeletionPreview:
    """Erase the account and everything only it holds. Returns what went."""
    preview = await deletion_preview(db, user)
    if preview.blocked_by:
        names = ", ".join(o.name for o in preview.blocked_by)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Pass ownership of {names} to someone else before deleting your account",
        )

    doomed = {o.slug for o in preview.organisations_deleted}
    for _, tenant in await _memberships(db, user.id):
        if tenant.tenant_type == "personal" or tenant.slug in doomed:
            await _delete_tenant(db, tenant.id)

    # Through the ORM, so every child collection -- experiences, educations,
    # certifications, languages, preferred roles and locations -- goes with it
    # by the relationships' own cascade.
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is not None:
        await db.delete(profile)
        await db.flush()

    await db.execute(
        update(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id).values(user_id=None)
    )
    await db.execute(delete(Membership).where(Membership.user_id == user.id))
    user_id = user.id
    db.expunge(user)
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    # After the commit: a session that survives a failed delete must still
    # work, and one revoked before the delete committed would not.
    await revoke_all_for_user(user_id)
    log.warning(
        "account.deleted",
        organisations_deleted=len(preview.organisations_deleted),
    )
    return preview


async def export_account(db: AsyncSession, user: User) -> dict[str, Any]:
    """Everything held about this person, as one JSON document.

    Their own organisations appear by name and role, not with every listing:
    a vacancy is the organisation's data, not the person's.
    """
    memberships = await _memberships(db, user.id)

    profile_out: dict[str, Any] | None = None
    profile = await db.scalar(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .options(selectinload(CandidateProfile.skills).selectinload(CandidateSkill.skill))
    )
    if profile is not None:
        profile_out = CandidateProfileFull.model_validate(profile).model_dump(mode="json")

    events = (
        await db.scalars(
            select(AnalyticsEvent)
            .where(AnalyticsEvent.user_id == user.id)
            .order_by(AnalyticsEvent.occurred_at)
        )
    ).all()

    log.info("account.exported")
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "privacy_notice_version": get_settings().privacy_notice_version,
        "account": {
            "id": str(user.id),
            "phone": user.phone,
            "email": user.email,
            "full_name": user.full_name,
            "phone_verified_at": _iso(user.phone_verified_at),
            "email_verified_at": _iso(user.email_verified_at),
            "preferred_locale": user.preferred_locale,
            "created_at": _iso(user.created_at),
            "consent_version": user.consent_version,
            "consented_at": _iso(user.consented_at),
        },
        "memberships": [
            {
                "organisation": tenant.name,
                "slug": tenant.slug,
                "type": tenant.tenant_type,
                "role": membership.role,
                "since": _iso(membership.created_at),
            }
            for membership, tenant in memberships
        ],
        "candidate_profile": profile_out,
        "activity": [
            {
                "event": event.name,
                "at": _iso(event.occurred_at),
                "subject_type": event.subject_type,
                "detail": event.payload,
            }
            for event in events
        ],
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
