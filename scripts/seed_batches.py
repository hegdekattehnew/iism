"""Demonstration batches for the four situations of ADR-102 (Sprint 103).

A training organisation sells courses, delivers training, or both, and a demonstration that shows
only a seller shows a quarter of the product. This script adds, **on top of `make seed`**, the other
three, so a cold start can show the whole of Epics B18 and B20:

* **Aarambh Skill Academy** sells *and* delivers: it runs two of its own courses at its own centres,
  with no authorisation (delivering what you sell is automatic).
* **Kaushal Partners** only delivers: three centres, and batches of a *seller's* courses, which
  it may run because that seller authorised it (the arrangement is created here through the
  product's own invitation, so it is a real approved row).
* **The seller** is the seeded course provider with the most published courses: seller only until
  this script authorises Kaushal Partners to deliver its courses.

The batches cover every state a person can meet: open with seats, starting this week, full, running,
finished, cancelled and a draft; a handful of learners from the demonstration candidates have
registered, some answered, some enrolled, one attended, one withdrawn, and **one waited more than
three days** so the reply reminder has something to find. The golden candidates
(`+919000000001` to `005`) are never written through: `make evaluate` asserts on them.

Everything goes through the product's own services (centres, delivery, batches, the learner's
registration), never a row written beside them, so a seeded batch obeys the invariants a real one
does. **Idempotent**: an organisation, a centre, a course or a batch that exists (by slug, or by
centre + course + label) is left alone. Dates are relative to today, so re-running next month adds
batches for next month and keeps the old.

Refuses to run on the scale or browser-test databases, whose contents the harnesses own.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import today_ist
from api.core.config import PRIVACY_NOTICE_VERSION, get_settings
from api.core.database import dispose_engine, get_sessionmaker
from api.modules.batches import learner as batch_learner
from api.modules.batches import learners as batch_learners
from api.modules.batches import service as batch_service
from api.modules.batches.models import Batch, BatchInterest
from api.modules.batches.schemas import BatchIn
from api.modules.centres.schemas import CentreIn
from api.modules.centres.service import create_centre
from api.modules.delivery import service as delivery
from api.modules.identity.models import Membership, Tenant, User
from api.modules.identity.service import provision_organisation
from api.modules.marketplace.models import Course, CourseSkill

ACADEMY = ("Aarambh Skill Academy", "aarambh@demo.iism.example", True, True)
PARTNER = ("Kaushal Partners", "kaushal@demo.iism.example", False, True)

# Where each organisation's centres are. A place the geography master does not know is kept as
# written and flagged, never guessed, so these are districts the master has.
ACADEMY_CENTRES = [
    ("Aarambh Kothrud", "Maharashtra", "Pune"),
    ("Aarambh Sitabuldi", "Maharashtra", "Nagpur"),
]
PARTNER_CENTRES = [
    ("Kaushal Hadapsar", "Maharashtra", "Pune"),
    ("Kaushal Gomti Nagar", "Uttar Pradesh", "Lucknow"),
    ("Kaushal Whitefield", "Karnataka", "Bengaluru Urban"),
]
# Learners are the demonstration candidates after the five the golden set is asserted on.
LEARNER_PHONES = [f"+9190000000{n:02d}" for n in range(6, 16)]


def _guard() -> None:
    name = get_settings().database_url.rsplit("/", 1)[-1]
    if name.endswith(("_scale", "_e2e")):
        sys.exit(f"refusing to seed demonstration batches into {name}: its harness owns the data")


async def _owner(
    db: AsyncSession, name: str, email: str, sells: bool, delivers: bool
) -> tuple[User, Tenant]:
    """The organisation and its owner, created the way sign-up does, or found."""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            full_name=f"{name} team",
            email_verified_at=datetime.now(UTC),
            consent_version=PRIVACY_NOTICE_VERSION,
            consented_at=datetime.now(UTC),
        )
        db.add(user)
        await db.flush()
        tenant = await provision_organisation(
            db, user, name, "course_provider", sells_courses=sells, delivers_training=delivers
        )
        await db.commit()
        return user, tenant
    found = await db.scalar(select(Tenant).where(Tenant.name == name))
    assert found is not None, f"{email} exists but {name} does not"
    return user, found


async def _centres(
    db: AsyncSession, org: Tenant, user: User, rows: list[tuple[str, str, str]]
) -> dict[str, Tenant]:
    centres: dict[str, Tenant] = {}
    for name, state, district in rows:
        found = await db.scalar(
            select(Tenant).where(Tenant.parent_id == org.id, Tenant.name == name)
        )
        centres[name] = found or await create_centre(
            db,
            org,
            user,
            CentreIn(name=name, state=state, district=district, address=f"{name}, {district}"),
        )
    return centres


async def _own_courses(db: AsyncSession, org: Tenant, sources: list[Course]) -> list[Course]:
    """Two published courses of the academy's own, cloned from seeded ones (skills and all), so a
    batch of them is a batch of something that teaches real standards."""
    made: list[Course] = []
    for src in sources:
        slug = f"aarambh-{src.slug}"[:120]
        course = await db.scalar(select(Course).where(Course.slug == slug))
        if course is None:
            course = Course(
                slug=slug,
                tenant_id=org.id,
                title=src.title,
                description=src.description,
                mode="offline",
                language=src.language,
                duration_hours=src.duration_hours,
                fee_inr=src.fee_inr,
                nsqf_level=src.nsqf_level,
                status="published",
            )
            db.add(course)
            await db.flush()
            links = (
                await db.scalars(select(CourseSkill).where(CourseSkill.course_id == src.id))
            ).all()
            for link in links:
                db.add(
                    CourseSkill(
                        course_id=course.id, skill_id=link.skill_id, level_taught=link.level_taught
                    )
                )
            await db.commit()
        made.append(course)
    return made


def _plan(course: Course, centre: Tenant, label: str, start: int, **over: Any) -> BatchIn:
    today = today_ist()
    return BatchIn(
        course_slug=course.slug,
        centre_slug=centre.slug,
        label=label,
        starts_on=today + timedelta(days=start),
        ends_on=today + timedelta(days=start + over.pop("length", 30)),
        seats=over.pop("seats", 20),
        mode=over.pop("mode", "in_person"),
        schedule=over.pop("schedule", "Mon to Fri, 9 to 1"),
        fee_inr=over.pop("fee", None),
    )


async def _batch(
    db: AsyncSession,
    org: Tenant,
    user: User,
    course: Course,
    centre: Tenant,
    label: str,
    start: int,
    *,
    publish: bool = True,
    **over: Any,
) -> Batch | None:
    """One batch, made through the single writer and published; skipped when it exists."""
    existing = await db.scalar(
        select(Batch).where(
            Batch.centre_id == centre.id, Batch.course_id == course.id, Batch.label == label
        )
    )
    if existing is not None:
        return None
    made = await batch_service.create_batch(
        db, org, user, _plan(course, centre, label, start, **over)
    )
    if publish:
        await batch_service.publish_batch(db, org, user, uuid.UUID(made.id))
    return await db.get(Batch, uuid.UUID(made.id))


async def _learners(db: AsyncSession) -> list[User]:
    users = list(
        (
            await db.scalars(
                select(User).where(User.phone.in_(LEARNER_PHONES)).order_by(User.phone)
            )
        ).all()
    )
    if len(users) < 8:
        sys.exit("the demonstration candidates are missing: run `make seed` first")
    return users


async def _register(
    db: AsyncSession, batch: Batch, user: User, message: str | None = None
) -> BatchInterest | None:
    from api.modules.marketplace.profile_service import ensure_profile

    profile = await ensure_profile(db, user.id)
    held = await db.scalar(
        select(BatchInterest).where(
            BatchInterest.batch_id == batch.id, BatchInterest.profile_id == profile.id
        )
    )
    if held is not None:
        return None
    await batch_learner.register(db, user, batch_id=batch.id, message=message)
    return await db.scalar(
        select(BatchInterest).where(
            BatchInterest.batch_id == batch.id, BatchInterest.profile_id == profile.id
        )
    )


async def main() -> int:
    _guard()
    stats = {"organisations": 0, "centres": 0, "courses": 0, "batches": 0, "learners": 0}
    async with get_sessionmaker()() as db:
        seller = await db.scalar(
            select(Tenant)
            .join(Course, Course.tenant_id == Tenant.id)
            .where(
                Tenant.tenant_type == "course_provider",
                Tenant.publishes_courses.is_(True),
                Course.status == "published",
                Tenant.name.not_in((ACADEMY[0], PARTNER[0])),
            )
            .group_by(Tenant.id)
            .order_by(func.count(Course.id).desc(), Tenant.slug)
            .limit(1)
        )
        if seller is None:
            sys.exit("no course provider with published courses: run `make seed` first")
        seller_courses = list(
            (
                await db.scalars(
                    select(Course)
                    .where(Course.tenant_id == seller.id, Course.status == "published")
                    .order_by(Course.slug)
                    .limit(3)
                )
            ).all()
        )
        if len(seller_courses) < 2:
            sys.exit(f"{seller.name} has fewer than two published courses: run `make seed` first")
        seller_owner = await db.scalar(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.tenant_id == seller.id, Membership.role == "owner")
            .order_by(User.created_at)
            .limit(1)
        )
        assert seller_owner is not None, f"{seller.name} has no owner: run `make seed` first"
        users = await _learners(db)

        academy_user, academy = await _owner(db, *ACADEMY)
        partner_user, partner = await _owner(db, *PARTNER)
        stats["organisations"] = 2
        academy_centres = await _centres(db, academy, academy_user, ACADEMY_CENTRES)
        partner_centres = await _centres(db, partner, partner_user, PARTNER_CENTRES)
        stats["centres"] = len(academy_centres) + len(partner_centres)
        own = await _own_courses(db, academy, seller_courses[:2])
        stats["courses"] = len(own)

        # The seller authorises the partner for all its courses: its invitation is its approval.
        arrangements = await delivery.arrangements_of(db, seller)
        if not any(
            a.other.slug == partner.slug and a.state == "approved" and a.course is None
            for a in arrangements.as_provider
        ):
            await delivery.invite_partner(
                db, provider=seller, actor=seller_owner, partner_slug=partner.slug, course_slug=None
            )

        k1, k2 = academy_centres.values()
        p1, p2, p3 = partner_centres.values()
        plans: list[tuple[Tenant, User, Course, Tenant, str, int, dict[str, Any]]] = [
            # Aarambh runs its own courses, no authorisation needed: open, starting this week.
            (academy, academy_user, own[0], k1, "Morning batch", 21, {}),
            (
                academy,
                academy_user,
                own[0],
                k2,
                "Evening batch",
                3,
                {"seats": 15, "mode": "hybrid"},
            ),
            (academy, academy_user, own[1], k1, "Weekend batch", 35, {"seats": 12}),
            # Kaushal runs the seller's courses.
            (partner, partner_user, seller_courses[0], p1, "Morning batch", 14, {"seats": 25}),
            (partner, partner_user, seller_courses[0], p2, "Day batch", 28, {"fee": 3500}),
            (
                partner,
                partner_user,
                seller_courses[1],
                p3,
                "Online evening",
                10,
                {"mode": "online"},
            ),
            (partner, partner_user, seller_courses[1], p1, "Small group", 18, {"seats": 2}),
            (partner, partner_user, seller_courses[0], p1, "Started last week", 5, {}),
            (partner, partner_user, seller_courses[1], p2, "Last term", 5, {}),
            (partner, partner_user, seller_courses[0], p3, "Cancelled by the centre", 40, {}),
        ]
        made: dict[str, Batch] = {}
        for org, user, course, centre, label, start, over in plans:
            batch = await _batch(db, org, user, course, centre, label, start, **over)
            if batch is not None:
                made[f"{org.slug}/{label}"] = batch
                stats["batches"] += 1
        await _batch(
            db, academy, academy_user, own[1], k2, "Draft: next quarter", 70, publish=False
        )

        async def mark(batch: Batch, interest: BatchInterest, new: str) -> None:
            await batch_learners.set_status(db, partner, partner_user, batch.id, interest.id, new)

        # Learners register while a batch can still be joined, then the dates move for the two that
        # are history (a batch cannot be planned in the past, so a seed cannot create one).
        morning = made.get(f"{partner.slug}/Morning batch")
        if morning is not None:
            for i, user in enumerate(users[:6]):
                interest = await _register(
                    db, morning, user, "Evenings are hard" if i == 0 else None
                )
                if interest is None:
                    continue
                stats["learners"] += 1
                if i == 1:
                    await mark(morning, interest, "contacted")
                elif i == 2:
                    await mark(morning, interest, "enrolled")
                elif i == 3:
                    await batch_learner.withdraw(db, user, interest.id)
                elif i == 4:  # waited past the promised three days, unanswered
                    await db.execute(
                        update(BatchInterest)
                        .where(BatchInterest.id == interest.id)
                        .values(created_at=func.now() - timedelta(days=5))
                    )
                    await db.commit()
        small = made.get(f"{partner.slug}/Small group")
        if small is not None:  # two seats, both taken: a full batch
            for user in users[6:8]:
                interest = await _register(db, small, user)
                if interest is not None:
                    stats["learners"] += 1
                    await mark(small, interest, "enrolled")
        running = made.get(f"{partner.slug}/Started last week")
        enrolled_here: list[BatchInterest] = []
        if running is not None:
            for user in users[8:10]:
                interest = await _register(db, running, user)
                if interest is not None:
                    stats["learners"] += 1
                    await mark(running, interest, "enrolled")
                    enrolled_here.append(interest)
        cancelled = made.get(f"{partner.slug}/Cancelled by the centre")
        if cancelled is not None:
            if await _register(db, cancelled, users[0]) is not None:
                stats["learners"] += 1
            await batch_service.cancel_batch(db, partner, partner_user, cancelled.id)

        today = today_ist()
        if running is not None:
            await db.execute(
                update(Batch)
                .where(Batch.id == running.id)
                .values(starts_on=today - timedelta(days=7), ends_on=today + timedelta(days=21))
            )
            await db.commit()
            if enrolled_here:  # the centre has taken the register once: one learner came
                await mark(running, enrolled_here[0], "attended")
        last_term = made.get(f"{partner.slug}/Last term")
        if last_term is not None:
            await db.execute(
                update(Batch)
                .where(Batch.id == last_term.id)
                .values(starts_on=today - timedelta(days=60), ends_on=today - timedelta(days=10))
            )
            await db.commit()

    await dispose_engine()
    print("seeded demonstration batches:", stats)
    print(f"  seller: {seller.name}; delivering only: {partner.name}; both: {academy.name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
