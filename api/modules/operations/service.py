"""The back office: what an operator may do, and the record of having done it.

Its own module, a leaf in the `privacy/` mould -- it depends on `identity`,
`marketplace` and, since Sprint 33, `matching` (for the programme report's
serious-match count), and nothing depends on it (ADR-014). Putting it in
`identity/` would invert that arrow the first time the queue needed a listing
count, which is day one: `marketplace` already imports `identity`, so the
cycle would be immediate.

The dangerous function lives here rather than in `scripts/grant_staff.py`, so
that granting operator authority is exercised by the ordinary test fixtures. A
bare script is the one shape that cannot be.
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import ORGANISATION_TYPES
from api.modules.applications.models import Application
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace.models import CandidateProfile, Course, Job
from api.modules.matching import match_jobs
from api.modules.matching.scoring import SERIOUS_MATCH_SCORE
from api.modules.operations.models import TenantVerificationEvent

log = structlog.get_logger("iism.ops")


async def unverified_organisations(
    db: AsyncSession, *, limit: int = 100
) -> list[tuple[Tenant, int, int, int]]:
    """Organisations waiting on a decision, oldest first.

    **Personal workspaces are excluded**, which is `ORGANISATION_TYPES`' lesson
    applied to a new query: every candidate owns one, so without the filter the
    queue would be a list of every job seeker on the platform presented as
    businesses awaiting verification.

    Oldest first because a queue that surfaces the newest arrival leaves its
    oldest entry unanswered for ever.
    """
    jobs = select(Job.tenant_id, func.count().label("n")).group_by(Job.tenant_id).subquery()
    courses = (
        select(Course.tenant_id, func.count().label("n")).group_by(Course.tenant_id).subquery()
    )
    members = (
        select(Membership.tenant_id, func.count().label("n"))
        .group_by(Membership.tenant_id)
        .subquery()
    )
    stmt = (
        select(
            Tenant,
            func.coalesce(jobs.c.n, 0),
            func.coalesce(courses.c.n, 0),
            func.coalesce(members.c.n, 0),
        )
        .outerjoin(jobs, jobs.c.tenant_id == Tenant.id)
        .outerjoin(courses, courses.c.tenant_id == Tenant.id)
        .outerjoin(members, members.c.tenant_id == Tenant.id)
        .where(Tenant.tenant_type.in_(ORGANISATION_TYPES), Tenant.verified_at.is_(None))
        .order_by(Tenant.created_at)
        .limit(limit)
    )
    return [(row[0], row[1], row[2], row[3]) for row in (await db.execute(stmt)).all()]


async def organisation_for_review(db: AsyncSession, slug: str) -> Tenant | None:
    """Any organisation, verified or not -- the detail view has to show both.

    Personal workspaces stay unreachable here for the same reason they are
    absent from the queue.
    """
    return await db.scalar(
        select(Tenant).where(Tenant.slug == slug, Tenant.tenant_type.in_(ORGANISATION_TYPES))
    )


async def verification_history(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[tuple[TenantVerificationEvent, str | None]]:
    """Every decision, newest first, with the actor's name where it survives."""
    stmt = (
        select(TenantVerificationEvent, User.full_name)
        .outerjoin(User, User.id == TenantVerificationEvent.actor_user_id)
        .where(TenantVerificationEvent.tenant_id == tenant_id)
        .order_by(TenantVerificationEvent.created_at.desc())
    )
    return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]


async def set_verification(
    db: AsyncSession, tenant: Tenant, *, decision: str, note: str, actor: User
) -> TenantVerificationEvent:
    """Record a decision, and project it onto the tenant.

    **The log is the source of truth and the tenant is the read path.** Both
    are written in one transaction. On `revoked` the tenant's three columns go
    NULL -- so the reason for a revocation survives only in the row appended
    here, which is why the two are not redundant.

    Idempotent by nature rather than by guard: granting an already-verified
    organisation appends a fresh decision with fresh evidence, which is a
    legitimate act (re-verification) and not a mistake to refuse.
    """
    event = TenantVerificationEvent(
        tenant_id=tenant.id, decision=decision, note=note, actor_user_id=actor.id
    )
    db.add(event)

    if decision == "granted":
        tenant.verified_at = func.now()
        tenant.verified_by = actor.id
        tenant.verification_note = note
    else:
        tenant.verified_at = None
        tenant.verified_by = None
        tenant.verification_note = None

    await db.commit()
    # The tenant's `verified_at` came from `func.now()`, so the instance holds
    # a SQL expression until it is read back.
    await db.refresh(tenant)
    await db.refresh(event)
    log.info("ops.verification", tenant_id=str(tenant.id), decision=decision)
    return event


async def set_staff(db: AsyncSession, *, address: str, staff: bool) -> User:
    """Grant or revoke operator authority. **Reachable only from a script.**

    No HTTP route in this product calls this, in this or any later revision
    (ADR-042): a back office whose first feature is its own escalation path is
    the failure that rule prevents. Running it needs database credentials,
    which is strictly more than the API grants anybody.

    **It refuses to create.** A script that can mint an account *and* make it
    staff is a one-command account takeover, so an unknown address is an error
    and nothing is written.

    The log line carries the user id and never the address -- the ADR-023
    redaction tail reads this stream too, but not leaking in the first place is
    cheaper than being masked.
    """
    key = address.strip().lower()
    user = await db.scalar(select(User).where(func.lower(User.email) == key))
    if user is None:
        user = await db.scalar(select(User).where(User.phone == address.strip()))
    if user is None:
        raise LookupError(f"no account for {address!r} -- this never creates one")

    user.is_staff = staff
    await db.commit()
    await db.refresh(user)
    log.warning("ops.staff_changed", user_id=str(user.id), is_staff=staff)
    return user


async def staff_roster(db: AsyncSession) -> list[User]:
    """Everyone holding operator authority.

    Printed after every grant, because "who else is staff" is exactly the
    question worth answering at the moment you add one -- and nothing else in
    the product answers it.
    """
    return list((await db.scalars(select(User).where(User.is_staff.is_(True)))).all())


@dataclass(frozen=True)
class ProgrammeReport:
    """What a government-agency programme has to show for itself so far.

    Enrolled and applied/hired are cheap counts; matched is not -- it calls the
    real scorer once per enrolled candidate, through `match_jobs`, the same
    function `/me/matches` uses (ADR-037: one scorer, never a second, looser
    "probably has a match" rule). Fine at programme scale (tens of candidates);
    were this ever run at thousands, it would need the same batching
    `matching.employer._candidates_for_jobs` already does the other direction.
    """

    programme: str
    enrolled: int
    matched: int
    applied: int
    hired: int


async def programme_report(db: AsyncSession, programme: str) -> ProgrammeReport:
    """Outcomes for one government-agency programme, by name.

    Unknown programme names are not an error -- there is no programme table to
    check against (see `CandidateProfile.enrolled_via_programme`'s docstring),
    so a typo simply reports zero rather than 404ing on a resource that was
    never a real entity to look up.
    """
    profile_ids = list(
        (
            await db.scalars(
                select(CandidateProfile.id).where(
                    CandidateProfile.enrolled_via_programme == programme
                )
            )
        ).all()
    )
    if not profile_ids:
        return ProgrammeReport(programme=programme, enrolled=0, matched=0, applied=0, hired=0)

    matched = 0
    for profile_id in profile_ids:
        scored = await match_jobs(db, profile_id)
        if any(s.result.score >= SERIOUS_MATCH_SCORE for s in scored):
            matched += 1

    applied = await db.scalar(
        select(func.count(func.distinct(Application.profile_id))).where(
            Application.profile_id.in_(profile_ids)
        )
    )
    hired = await db.scalar(
        select(func.count(func.distinct(Application.profile_id))).where(
            Application.profile_id.in_(profile_ids), Application.status == "hired"
        )
    )
    return ProgrammeReport(
        programme=programme,
        enrolled=len(profile_ids),
        matched=matched,
        applied=applied or 0,
        hired=hired or 0,
    )
