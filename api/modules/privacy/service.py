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
from typing import Any, cast

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.config import get_settings
from api.core.security import revoke_all_for_user
from api.modules.alerts.models import JobAlert
from api.modules.analytics.models import AnalyticsEvent
from api.modules.applications.models import Application, SavedJob
from api.modules.identity import Invitation, Membership, Tenant, User
from api.modules.interests.models import CourseInterest
from api.modules.marketplace.models import (
    CandidateProfile,
    CandidateSkill,
    Course,
    CourseSkill,
    Job,
    JobSkill,
)
from api.modules.marketplace.schemas import CandidateProfileFull
from api.modules.notifications.models import Notification
from api.modules.operations.models import TenantVerificationEvent
from api.modules.privacy.schemas import (
    DeletionPreview,
    OrganisationDeletionPreview,
    OrganisationFate,
)

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
    # What people did with this organisation's listings, deleted explicitly.
    # Until Sprint 24 these two went only by the FK cascade from `jobs.id` --
    # against this module's own rule, and against a comment below claiming they
    # were already removed "exactly like the applications above", which were
    # not there. The cascade did the right thing; nothing said so.
    await db.execute(delete(Application).where(Application.job_id.in_(job_ids)))
    await db.execute(delete(SavedJob).where(SavedJob.job_id.in_(job_ids)))
    # Who was told about this organisation's vacancies. Explicitly, like
    # everything else here -- the FK cascades, and "everything went" is the one
    # claim an erasure path must never make on assumption.
    await db.execute(delete(JobAlert).where(JobAlert.job_id.in_(job_ids)))
    await db.execute(delete(JobSkill).where(JobSkill.job_id.in_(job_ids)))
    await db.execute(delete(Job).where(Job.tenant_id == tenant_id))
    await db.execute(delete(CourseInterest).where(CourseInterest.course_id.in_(course_ids)))
    await db.execute(delete(CourseSkill).where(CourseSkill.course_id.in_(course_ids)))
    await db.execute(delete(Course).where(Course.tenant_id == tenant_id))
    # No foreign key to cascade from -- the outbox names a recipient by id
    # rather than pointing at one (see its module docstring) -- so erasure
    # removes them explicitly, like the rows above.
    await db.execute(
        delete(Notification).where(
            Notification.recipient_kind == "tenant", Notification.recipient_id == tenant_id
        )
    )
    # Explicitly, like everything above: the FK cascades, and "everything went"
    # is the one claim an erasure path must never make on assumption. An
    # invitation is also the single row in this product that stores somebody
    # else's address, so leaving one behind would leave a stranger's mailbox in
    # a table belonging to an organisation that no longer exists.
    await db.execute(delete(Invitation).where(Invitation.tenant_id == tenant_id))
    # The twelfth table (Sprint 28). **The organisation is the subject of these
    # rows, not a third party**: once it is gone, "an organisation that no
    # longer exists was verified on a date" identifies nobody, defends nothing,
    # and is data kept without a purpose. Explicitly, like everything above.
    #
    # The consequence is real and is not solved here: a verified organisation
    # can misbehave, delete itself and register again under the same name,
    # because the duplicate-name guard is per account. Closing that needs a
    # tombstone that survives erasure, which is a fresh DPDP decision.
    await db.execute(
        delete(TenantVerificationEvent).where(TenantVerificationEvent.tenant_id == tenant_id)
    )
    await db.execute(delete(Membership).where(Membership.tenant_id == tenant_id))
    await db.execute(delete(Tenant).where(Tenant.id == tenant_id))


async def organisation_deletion_preview(
    db: AsyncSession, tenant: Tenant, viewer: User
) -> OrganisationDeletionPreview:
    """What deleting this one organisation would take with it. Changes nothing."""
    job_ids = select(Job.id).where(Job.tenant_id == tenant.id)
    course_ids = select(Course.id).where(Course.tenant_id == tenant.id)

    async def count(model, *where) -> int:  # type: ignore[no-untyped-def]
        return (await db.scalar(select(func.count()).select_from(model).where(*where))) or 0

    return OrganisationDeletionPreview(
        slug=tenant.slug,
        name=tenant.name,
        tenant_type=tenant.tenant_type,
        jobs=await count(Job, Job.tenant_id == tenant.id),
        courses=await count(Course, Course.tenant_id == tenant.id),
        applications=await count(Application, Application.job_id.in_(job_ids)),
        course_interests=await count(CourseInterest, CourseInterest.course_id.in_(course_ids)),
        # **Excluding the caller.** They are about to delete it; counting
        # themselves among the people who lose access would tell a sole owner
        # that one other person is affected, which is nobody.
        other_members=await count(
            Membership, Membership.tenant_id == tenant.id, Membership.user_id != viewer.id
        ),
    )


async def delete_organisation(db: AsyncSession, user: User, tenant: Tenant) -> None:
    """Delete one organisation, and leave the account and its others alone.

    **This route did not exist until it was reported missing**, and its absence
    was a trap rather than an omission: `POST /org/{slug}/leave` refuses the
    only owner (Sprint 25, correctly -- an organisation must not be left with
    nobody in charge), so somebody who created an organisation by mistake had
    exactly one way out, `DELETE /me/account`, which takes the account and
    every *other* organisation with it. Creating was one request; undoing it
    was impossible.

    **Through `_delete_tenant`, not beside it.** That function is the one place
    that knows everything a tenant owns -- listings, applications, interests,
    invitations, notifications, memberships, job alerts -- and a second copy
    here is how one of them starts being missed.

    Live applicants are told, which closes a gap recorded since Sprint 24:
    until now an organisation could vanish and the people waiting on it heard
    nothing at all.
    """
    await _tell_applicants_the_organisation_is_gone(db, tenant)
    await _delete_tenant(db, tenant.id)
    await db.commit()
    # WARNING, not INFO: irreversible, owner-only, and it is what somebody goes
    # looking for after "our organisation disappeared".
    log.warning("organisation.deleted", org_slug=tenant.slug, by_user=str(user.id))


async def _tell_applicants_the_organisation_is_gone(db: AsyncSession, tenant: Tenant) -> None:
    """Tell the people still waiting on this organisation's vacancies.

    Only `applied` and `shortlisted`: somebody rejected has been told, somebody
    hired does not need this, and a withdrawn applicant took themselves out.

    **Queued before the delete, in the same transaction.** The notification
    names a *user*, not the tenant, so it survives the organisation it is about
    -- which is the point. `vacancy_closed` is reused rather than given a
    near-identical sibling: what the applicant needs to know is the same in
    both cases, which is that the vacancy is not coming back.
    """
    from api.modules.notifications import enqueue

    rows = await db.execute(
        select(Job.title, CandidateProfile.user_id)
        .join(Application, Application.job_id == Job.id)
        .join(CandidateProfile, CandidateProfile.id == Application.profile_id)
        .where(
            Job.tenant_id == tenant.id,
            Application.status.in_(("applied", "shortlisted")),
        )
    )
    for title, user_id in rows.all():
        await enqueue(
            db,
            recipient_kind="user",
            recipient_id=user_id,
            channel="in_app",
            template="vacancy_closed",
            payload={"vacancy": title, "path": "/applications"},
        )


async def delete_account(db: AsyncSession, user: User) -> DeletionPreview:
    """Erase the account and everything only it holds. Returns what went."""
    preview = await deletion_preview(db, user)
    if preview.blocked_by:
        names = ", ".join(o.name for o in preview.blocked_by)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            # Until Sprint 25 this sentence named something the product could
            # not do: there was no way to make anybody else an owner, because
            # there was no way to have a second member at all. Worse, the guard
            # itself was unreachable -- it needs another member to exist -- so
            # a sole owner deleting their account destroyed the organisation,
            # its listings and every application to them, silently. Now the
            # instruction is an action: `PATCH /org/{slug}/members/{user_id}`.
            f"Make somebody else an owner of {names} before deleting your account",
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
        # Explicitly, before the profile itself. Both cascade from it in the
        # database, but "everything went" is the one claim an erasure path must
        # never make on assumption -- and an employer's inbox losing this
        # applicant entirely is the point.
        await db.execute(delete(Application).where(Application.profile_id == profile.id))
        await db.execute(delete(SavedJob).where(SavedJob.profile_id == profile.id))
        await db.execute(delete(CourseInterest).where(CourseInterest.profile_id == profile.id))
        await db.execute(delete(JobAlert).where(JobAlert.profile_id == profile.id))
        await db.delete(profile)
        await db.flush()

    await db.execute(
        update(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id).values(user_id=None)
    )
    # Unlike an analytics row, a notification is *addressed* to this person: it
    # cannot be anonymised by dropping the link, so it goes.
    await db.execute(
        delete(Notification).where(
            Notification.recipient_kind == "user", Notification.recipient_id == user.id
        )
    )
    # An invitation addressed to an account being erased is withdrawn rather
    # than left live: accepting it later would recreate a membership for a
    # person who asked to be forgotten.
    if user.email:
        await db.execute(
            delete(Invitation).where(func.lower(Invitation.email) == user.email.lower())
        )
    # Invitations this person *sent* survive -- they belong to the organisation,
    # which still exists and may still be expecting the people it invited.
    # `invited_by_user_id` is ON DELETE SET NULL for exactly this, so the row
    # stops naming them without the offer evaporating mid-flight.
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

    applications = (
        await db.scalars(
            select(Application)
            .where(Application.profile_id == profile.id)
            .order_by(Application.created_at)
        )
        if profile is not None
        else None
    )
    saved = (
        await db.scalars(
            select(SavedJob).where(SavedJob.profile_id == profile.id).order_by(SavedJob.created_at)
        )
        if profile is not None
        else None
    )
    interests = (
        await db.scalars(
            select(CourseInterest)
            .where(CourseInterest.profile_id == profile.id)
            .order_by(CourseInterest.created_at)
        )
        if profile is not None
        else None
    )

    events = (
        await db.scalars(
            select(AnalyticsEvent)
            .where(AnalyticsEvent.user_id == user.id)
            .order_by(AnalyticsEvent.occurred_at)
        )
    ).all()

    # Invitations this person sent. Theirs to see, because they are the act --
    # and the addresses are ones they typed themselves. Invitations sent *to*
    # them are deliberately absent: those are the sending organisation's
    # record, and listing them here would tell somebody every organisation that
    # ever considered them.
    sent_invitations = (
        await db.scalars(
            select(Invitation)
            .where(Invitation.invited_by_user_id == user.id)
            .order_by(Invitation.created_at)
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
        # What this person asked for, and what they were told about it. The
        # disclosure each application carried is part of their record, not only
        # the employer's.
        "applications": [
            {
                "vacancy": application.job.title,
                # `Job.tenant` is typed `object` on the model; the cast is at the
                # read, not a change to the mapping.
                "organisation": cast(Tenant, application.job.tenant).name,
                "status": application.status,
                "message": application.message,
                "applied_at": _iso(application.created_at),
                "contact_shared_at": _iso(application.contact_shared_at),
                "contact_revoked_at": _iso(application.contact_revoked_at),
            }
            for application in (applications.all() if applications is not None else [])
        ],
        "saved_jobs": [
            {"vacancy": row.job.title, "saved_at": _iso(row.created_at)}
            for row in (saved.all() if saved is not None else [])
        ],
        # The disclosure is part of the learner's own record, not only the
        # provider's -- the same reason applications carry their two timestamps.
        "course_interests": [
            {
                "course": interest.course.title,
                "provider": cast(Tenant, interest.course.tenant).name,
                "status": interest.status,
                "message": interest.message,
                "registered_at": _iso(interest.created_at),
                "contact_shared_at": _iso(interest.contact_shared_at),
                "contact_revoked_at": _iso(interest.contact_revoked_at),
            }
            for interest in (interests.all() if interests is not None else [])
        ],
        # Invitations this person sent, with what became of each. The state is
        # derived from the timestamps by the model, so this export cannot
        # disagree with what the organisation's own screen shows.
        "invitations_sent": [
            {
                "organisation": invitation.tenant.name,
                "email": invitation.email,
                "role": invitation.role,
                "state": invitation.state(datetime.now(UTC)),
                "sent_at": _iso(invitation.created_at),
                "expires_at": _iso(invitation.expires_at),
                "accepted_at": _iso(invitation.accepted_at),
                "revoked_at": _iso(invitation.revoked_at),
            }
            for invitation in sent_invitations
        ],
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
