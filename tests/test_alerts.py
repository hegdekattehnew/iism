"""The job-alert sweep (Sprint 27): the worker's own matcher run as a cron.

No test file existed for this before -- `sweep()` had zero coverage, cron
registration aside (`test_worker_schedule.py`). It also had a real N+1: one
`db.get(User, ...)` per eligible candidate, nested inside the per-job loop, up
to 250 individual lookups for ten jobs times twenty-five candidates. The fix
batches that lookup per job; the regression test below is what keeps it fixed.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.alerts.models import JobAlert
from api.modules.alerts.service import sweep
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, CandidateSkill, Job, JobSkill
from api.modules.notifications.models import Notification
from api.modules.skills.models import Skill


async def _skill(db: AsyncSession, slug: str) -> Skill:
    skill = Skill(
        slug=slug,
        name="Handle alert sweep records",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code=f"TST/{slug.upper()}",
        source="nsqf",
    )
    db.add(skill)
    await db.flush()
    return skill


async def _job(db: AsyncSession, tenant_id: uuid.UUID, skill_id: uuid.UUID, slug: str) -> Job:
    job = Job(slug=slug, tenant_id=tenant_id, title="Ward attendant", status="published")
    db.add(job)
    await db.flush()
    db.add(JobSkill(job_id=job.id, skill_id=skill_id, importance=4, is_mandatory=True))
    await db.commit()
    return job


async def _candidate(
    db: AsyncSession, skill_id: uuid.UUID, n: int, *, email: str | None = None, enabled: bool = True
) -> CandidateProfile:
    user = User(phone=f"+9199300{n:05d}", email=email)
    db.add(user)
    await db.flush()
    profile = CandidateProfile(
        user_id=user.id, headline=f"candidate-{n}", years_experience=1, job_alerts_enabled=enabled
    )
    db.add(profile)
    await db.flush()
    db.add(CandidateSkill(profile_id=profile.id, skill_id=skill_id, proficiency=3))
    await db.commit()
    return profile


async def test_a_matched_candidate_is_alerted_once(db: AsyncSession) -> None:
    """A candidate holding the one mandatory standard is told in-app and by
    email, and a second sweep does not tell them again -- `JobAlert`'s unique
    constraint is what makes "told once, ever" a fact rather than an intention.
    """
    skill = await _skill(db, "alert-sweep-single")
    tenant = Tenant(slug="alert-sweep-employer", name="Sweep Hospital", tenant_type="employer")
    db.add(tenant)
    await db.flush()
    job = await _job(db, tenant.id, skill.id, "alert-sweep-single-job")
    candidate = await _candidate(db, skill.id, 1, email="candidate1@example.test")

    result = await sweep(db)
    assert result.jobs == 1
    assert result.alerts == 1

    alerts = (await db.scalars(select(JobAlert))).all()
    assert [a.profile_id for a in alerts] == [candidate.id]

    notifications = (await db.scalars(select(Notification))).all()
    channels = sorted(n.channel for n in notifications)
    assert channels == ["email", "in_app"]
    assert all(n.template == "job_alert" for n in notifications)
    assert all(n.recipient_id == candidate.user_id for n in notifications)

    await db.refresh(job)
    assert job.alerted_at is not None

    # A second sweep finds no un-alerted jobs at all -- `alerted_at` was
    # stamped on the first run, before anything was queued.
    again = await sweep(db)
    assert again == type(again)()


async def test_an_opted_out_candidate_is_not_alerted(db: AsyncSession) -> None:
    skill = await _skill(db, "alert-sweep-optout")
    tenant = Tenant(slug="alert-sweep-optout-employer", name="Quiet Clinic", tenant_type="employer")
    db.add(tenant)
    await db.flush()
    await _job(db, tenant.id, skill.id, "alert-sweep-optout-job")
    await _candidate(db, skill.id, 2, enabled=False)

    result = await sweep(db)
    assert result.alerts == 0
    assert result.skipped_opted_out == 1
    assert (await db.scalars(select(JobAlert))).all() == []


async def test_the_sweep_does_not_query_once_per_candidate(db: AsyncSession) -> None:
    """The regression test. `_users_by_id` batches the per-candidate lookup
    `sweep()` used to run through `db.get(User, ...)`; the number of SELECTs
    one job's sweep issues must not grow with the size of its eligible pool.
    """
    from sqlalchemy import event

    skill = await _skill(db, "alert-sweep-scale")
    tenant = Tenant(
        slug="alert-sweep-scale-employer", name="Scale Hospital", tenant_type="employer"
    )
    db.add(tenant)
    await db.flush()

    statements: list[str] = []

    def count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        if statement.strip().upper().startswith("SELECT"):
            statements.append(statement)

    async def measure(job: Job) -> int:
        statements.clear()
        connection = (await db.connection()).sync_connection
        assert connection is not None
        event.listen(connection, "before_cursor_execute", count)
        try:
            await sweep(db, limit=10)
        finally:
            event.remove(connection, "before_cursor_execute", count)
        assert job.alerted_at is not None  # the sweep actually ran on this job
        return len(statements)

    await _candidate(db, skill.id, 3)
    await _candidate(db, skill.id, 4)
    job_two = await _job(db, tenant.id, skill.id, "alert-sweep-scale-two")
    two = await measure(job_two)

    for n in (5, 6, 7, 8, 9):
        await _candidate(db, skill.id, n)
    job_seven = await _job(db, tenant.id, skill.id, "alert-sweep-scale-seven")
    seven = await measure(job_seven)

    assert two == seven, f"{two} SELECTs for 2 candidates, {seven} for 7"
