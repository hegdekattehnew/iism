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
from collections import Counter
from dataclasses import dataclass, field

import structlog
from fastapi import HTTPException, status
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.authorization import ORGANISATION_TYPES
from api.modules.applications.models import WAS_HIRED_STATUSES, Application
from api.modules.geography.models import District, State
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace import record_verified_skill
from api.modules.marketplace.models import (
    CandidateCertification,
    CandidateProfile,
    Course,
    Job,
    posted_job,
)
from api.modules.matching import ScarceSkill, market_scarce_skills, match_jobs
from api.modules.matching.scoring import SERIOUS_MATCH_SCORE
from api.modules.notifications import enqueue
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
    was_verified = tenant.verified_at is not None
    event = TenantVerificationEvent(
        tenant_id=tenant.id, decision=decision, note=note, actor_user_id=actor.id
    )
    db.add(event)

    # **Told only when the badge actually changes** (Sprint 43, BL-9.2). A re-grant
    # of an organisation that is already verified is a legitimate act and changes
    # nothing the organisation can see; a revoke of one that never had the badge
    # likewise. Mailing either would teach people to ignore the one email that
    # means something. Queued before the commit, in the same transaction: a notice
    # that failed to queue must not leave a badge changed with nobody told.
    #
    # The payload is the organisation's name and a link, and nothing else: the
    # operator's note is evidence, not something to read out in an email, and an
    # address is resolved at send time (ADR-023). Email only -- an organisation's
    # members have no in-app inbox. An owner who signed up by phone alone has no
    # address, so the row is marked skipped and that organisation is not told.
    if decision == "granted" and not was_verified:
        template = "organisation_verified"
    elif decision != "granted" and was_verified:
        template = "organisation_verification_revoked"
    else:
        template = None
    if template is not None:
        await enqueue(
            db,
            recipient_kind="tenant",
            recipient_id=tenant.id,
            channel="email",
            template=template,
            payload={"organisation": tenant.name, "path": f"/employer/{tenant.slug}/settings"},
        )

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


async def unverified_certifications(
    db: AsyncSession, *, limit: int = 100
) -> list[tuple[CandidateCertification, str | None]]:
    """The queue: certifications naming a standard (`skill_id IS NOT NULL`)
    that nobody has verified yet (Sprint 35, BL-3.2).

    A certification naming no standard has nothing for this queue to decide
    -- there is no `CandidateSkill` write it could ever produce -- so it is
    excluded rather than shown with a decision that cannot be made.
    """
    stmt = (
        select(CandidateCertification, User.full_name)
        .join(CandidateProfile, CandidateCertification.profile_id == CandidateProfile.id)
        .join(User, CandidateProfile.user_id == User.id)
        .where(
            CandidateCertification.skill_id.is_not(None),
            CandidateCertification.verified_at.is_(None),
        )
        .order_by(CandidateCertification.id)
        .limit(limit)
    )
    return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]


async def certification_for_review(
    db: AsyncSession, certification_id: uuid.UUID
) -> CandidateCertification | None:
    # `profile` has no eager-load option on the model (only `skill` does,
    # since every read of a certification touches it) -- loaded explicitly
    # here because `verify_certification` reads `certification.profile` in
    # an async context, where a lazy load raises `MissingGreenlet`.
    return await db.scalar(
        select(CandidateCertification)
        .where(CandidateCertification.id == certification_id)
        .options(selectinload(CandidateCertification.profile))
    )


async def verify_certification(
    db: AsyncSession, certification: CandidateCertification, *, note: str, actor: User
) -> CandidateCertification:
    """The one non-seed writer of `source='certified'` BL-3.2 asks for.

    Denormalised onto the certification row alone (see its model docstring
    for why this is simpler than `tenant_verification_events` on purpose).
    Goes through `record_verified_skill` -- `marketplace`'s one public seam
    onto `_write_skills` -- rather than constructing a `CandidateSkill` here,
    so there remains exactly one construction site regardless of which
    module the write originates from.
    """
    if certification.skill_id is None or certification.skill is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This certification names no standard -- there is nothing to verify it against",
        )
    certification.verified_at = func.now()
    certification.verified_by = actor.id
    certification.verification_note = note

    # `record_verified_skill` commits; that single commit also persists the
    # three column assignments above, in the same transaction as the skill
    # write -- both or neither, which is the property that matters here.
    await record_verified_skill(
        db, certification.profile, certification.skill.slug, source="certified"
    )
    await db.refresh(certification)
    log.info("ops.certification_verified", certification_id=str(certification.id))
    return certification


async def set_staff(
    db: AsyncSession, *, address: str, staff: bool, tier: str | None = None
) -> User:
    """Grant or revoke operator authority. **Reachable only from a script.**

    No HTTP route in this product calls this, in this or any later revision
    (ADR-042): a back office whose first feature is its own escalation path is
    the failure that rule prevents. Running it needs database credentials,
    which is strictly more than the API grants anybody.

    **It refuses to create.** A script that can mint an account *and* make it
    staff is a one-command account takeover, so an unknown address is an error
    and nothing is written.

    **A grant requires a tier; a revoke clears it** (Sprint 37, BL-7.3,
    ADR-044). `ck_users_staff_tier_pairs_with_flag` would refuse the write
    anyway if the two ever disagreed -- this just fails with a clearer message
    before asking the database to.

    The log line carries the user id and never the address -- the ADR-023
    redaction tail reads this stream too, but not leaking in the first place is
    cheaper than being masked.
    """
    if staff and tier is None:
        raise ValueError("granting operator authority requires a tier")

    key = address.strip().lower()
    user = await db.scalar(select(User).where(func.lower(User.email) == key))
    if user is None:
        user = await db.scalar(select(User).where(User.phone == address.strip()))
    if user is None:
        raise LookupError(f"no account for {address!r} -- this never creates one")

    user.is_staff = staff
    user.staff_tier = tier if staff else None
    await db.commit()
    await db.refresh(user)
    log.warning(
        "ops.staff_changed", user_id=str(user.id), is_staff=staff, staff_tier=user.staff_tier
    )
    return user


async def staff_roster(db: AsyncSession) -> list[User]:
    """Everyone holding operator authority.

    Printed after every grant, because "who else is staff" is exactly the
    question worth answering at the moment you add one -- and nothing else in
    the product answers it.
    """
    return list((await db.scalars(select(User).where(User.is_staff.is_(True)))).all())


@dataclass(frozen=True)
class PlatformDashboard:
    """An operator's first real landing screen (Sprint 39, BL-10.4) -- today
    there is none; `/admin` opens straight onto the verification queue with no
    orientation above it.

    The two queue counts are the same filters `unverified_organisations`/
    `unverified_certifications` already use, counted rather than loaded in
    full -- a dashboard tile does not need the rows, only how many.
    """

    unverified_organisations: int
    unverified_certifications: int
    organisations: int
    candidates: int
    published_jobs: int
    published_courses: int
    # What the whole market asks for that the candidate pool cannot supply
    # (Sprint 40) -- `market_scarce_skills()` reused rather than restated, the
    # same shortage a course provider's own dashboard could act on.
    scarce_skills: list[ScarceSkill] = field(default_factory=list)


async def platform_dashboard(db: AsyncSession) -> PlatformDashboard:
    unverified_orgs = await db.scalar(
        select(func.count())
        .select_from(Tenant)
        .where(Tenant.tenant_type.in_(ORGANISATION_TYPES), Tenant.verified_at.is_(None))
    )
    unverified_certs = await db.scalar(
        select(func.count())
        .select_from(CandidateCertification)
        .where(
            CandidateCertification.skill_id.is_not(None),
            CandidateCertification.verified_at.is_(None),
        )
    )
    organisations = await db.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.tenant_type.in_(ORGANISATION_TYPES))
    )
    candidates = await db.scalar(select(func.count()).select_from(CandidateProfile))
    published_jobs = await db.scalar(select(func.count()).select_from(Job).where(posted_job()))
    published_courses = await db.scalar(
        select(func.count()).select_from(Course).where(Course.status == "published")
    )
    scarce = await market_scarce_skills(db)
    return PlatformDashboard(
        unverified_organisations=unverified_orgs or 0,
        unverified_certifications=unverified_certs or 0,
        organisations=organisations or 0,
        candidates=candidates or 0,
        published_jobs=published_jobs or 0,
        published_courses=published_courses or 0,
        scarce_skills=scarce,
    )


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
            Application.profile_id.in_(profile_ids),
            Application.status.in_(WAS_HIRED_STATUSES),
        )
    )
    return ProgrammeReport(
        programme=programme,
        enrolled=len(profile_ids),
        matched=matched,
        applied=applied or 0,
        hired=hired or 0,
    )


async def known_programmes(db: AsyncSession) -> list[str]:
    """Every distinct programme name a candidate is actually enrolled under.

    `programme_report` takes free text because there is no programme table to
    validate against -- but an operator who does not already know the exact
    string still needs somewhere to start. This is that list, not a second
    source of truth: a name here is exactly a value
    `CandidateProfile.enrolled_via_programme` holds, nothing more.
    """
    rows = await db.scalars(
        select(distinct(CandidateProfile.enrolled_via_programme))
        .where(CandidateProfile.enrolled_via_programme.is_not(None))
        .order_by(CandidateProfile.enrolled_via_programme)
    )
    return [r for r in rows.all() if r is not None]


@dataclass(frozen=True)
class DistrictBreakdown:
    """How many of one programme's enrolled candidates live in one district."""

    district: str
    enrolled: int


async def programme_by_district(db: AsyncSession, programme: str) -> list[DistrictBreakdown]:
    """Enrolled candidates for one programme, grouped by district (Sprint 40).

    A genuinely new aggregation, not folded into `programme_report`: that
    function already pays for a per-candidate `match_jobs` loop (its own
    docstring names the cost), and a caller who wants only the four headline
    numbers should not also pay for this `GROUP BY` every time.

    A candidate with no resolved `district_id` rolls up into `"Unknown"`
    rather than being dropped, so the bars this feeds still sum to
    `programme_report`'s own `enrolled` count for the same programme --
    **no id is better than a wrong one**, but a candidate is not invisible
    just because their district never resolved.
    """
    # Grouped by the district's id, not its name: three names (Bilaspur,
    # Hamirpur, Pratapgarh) belong to two districts each, and eight districts
    # carry no name at all, so grouping on the name merged unrelated places.
    rows = (
        await db.execute(
            select(District.id, District.name, State.name, func.count(CandidateProfile.id))
            .select_from(CandidateProfile)
            .outerjoin(District, District.id == CandidateProfile.district_id)
            .outerjoin(State, State.id == District.state_id)
            .where(CandidateProfile.enrolled_via_programme == programme)
            .group_by(District.id, District.name, State.name)
        )
    ).all()
    # Two bars both called "Bilaspur" tell the reader nothing, so a name that
    # appears twice carries its state.
    seen = Counter(name for _id, name, _state, _n in rows if name)
    result = [
        DistrictBreakdown(
            district=(f"{name} ({state})" if seen[name] > 1 else name) if name else "Unknown",
            enrolled=count,
        )
        for _id, name, state, count in rows
    ]
    # Most enrolled first, so the bars read like a ranking rather than an
    # alphabetical list.
    result.sort(key=lambda d: (-d.enrolled, d.district))
    return result
