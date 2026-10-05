"""The employer's inbox, and what shares its loads, at volume (Sprint 50).

A shortlist click re-ran the whole inbox -- load and score every applicant -- to return the one
row that changed: 3.5 s at 5,000 applicants. And every profile load fetched its seven eager
collections, which nothing here reads. These hold the fixes to the same answers the slow paths
gave, and to the number of statements, which is what scales.
"""

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.applications.employer_service import inbox, set_status_and_reload
from api.modules.applications.models import Application
from api.modules.matching.employer import score_profiles
from api.modules.matching.service import candidate_facts
from tests.test_retrieval import _candidate, _employer, _job, _skill


async def _count[T](db: AsyncSession, call: Callable[[], Awaitable[T]]) -> tuple[int, T]:
    statements: list[str] = []

    def record(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    connection = (await db.connection()).sync_connection
    assert connection is not None
    event.listen(connection, "before_cursor_execute", record)
    try:
        result = await call()
    finally:
        event.remove(connection, "before_cursor_execute", record)
    return len(statements), result


async def _vacancy_with_applicants(db: AsyncSession, n: int, tag: str):  # type: ignore[no-untyped-def]
    skill = _skill(hash(tag) % 10_000)
    skill.slug = f"inbox-{tag}"
    skill.nos_code = f"INB/{tag}"
    db.add(skill)
    await db.flush()
    tenant = await _employer(db, f"inbox-employer-{tag}")
    job = await _job(db, tenant, f"inbox-job-{tag}", [(skill, 3, False)])
    applications = []
    for i in range(n):
        profile = await _candidate(db, hash((tag, i)) % 10_000_000, [(skill, "certified")])
        application = Application(job_id=job.id, profile_id=profile.id, status="applied")
        db.add(application)
        applications.append(application)
    await db.commit()
    return tenant, job, applications


async def test_a_status_change_returns_the_row_the_inbox_would_have(db: AsyncSession) -> None:
    tenant, job, applications = await _vacancy_with_applicants(db, 5, "same")
    target = applications[2]

    application, profile, user, result = await set_status_and_reload(
        db, tenant.id, job.slug, target.id, "shortlisted"
    )
    _job, rows = await inbox(db, tenant.id, job.slug)
    expected = next(r for r in rows if r[0].id == target.id)

    assert application.status == "shortlisted"
    assert (application.id, profile.id, user.id) == (expected[0].id, expected[1].id, expected[2].id)
    assert result.score == expected[3].score
    assert [m.name for m in result.matched] == [m.name for m in expected[3].matched]


async def test_a_status_change_costs_the_same_for_three_applicants_or_thirty(
    db: AsyncSession,
) -> None:
    tenant_a, job_a, apps_a = await _vacancy_with_applicants(db, 3, "few")
    tenant_b, job_b, apps_b = await _vacancy_with_applicants(db, 30, "many")

    few, _ = await _count(
        db, lambda: set_status_and_reload(db, tenant_a.id, job_a.slug, apps_a[0].id, "shortlisted")
    )
    many, _ = await _count(
        db, lambda: set_status_and_reload(db, tenant_b.id, job_b.slug, apps_b[0].id, "shortlisted")
    )

    assert few == many, f"{few} statements with 3 applicants, {many} with 30"


async def test_the_inbox_issues_the_same_statements_for_three_applicants_or_thirty(
    db: AsyncSession,
) -> None:
    """The profiles are loaded column-only: no query per collection, however many applicants."""
    tenant_a, job_a, _ = await _vacancy_with_applicants(db, 3, "ifew")
    tenant_b, job_b, _ = await _vacancy_with_applicants(db, 30, "imany")

    few, (_, rows_few) = await _count(db, lambda: inbox(db, tenant_a.id, job_a.slug))
    many, (_, rows_many) = await _count(db, lambda: inbox(db, tenant_b.id, job_b.slug))

    assert (len(rows_few), len(rows_many)) == (3, 30)
    assert few == many, f"{few} statements for 3, {many} for 30"
    # The vacancy and its standards load eagerly (about nine statements, however many applicants);
    # before this the profiles' collections added seven more *per page of them*.
    assert many <= 12, many


async def test_scoring_named_applicants_is_not_bounded_by_the_bind_limit(
    db: AsyncSession,
) -> None:
    """asyncpg refuses a statement with more than 32,767 parameters. A vacancy can draw more
    applicants than that; the lookup of their facts must not be one `IN`."""
    _tenant, job, _ = await _vacancy_with_applicants(db, 1, "bind")
    out = await score_profiles(db, job, [uuid.uuid4() for _ in range(40_000)])
    assert len(out) == 40_000


async def test_the_matching_facts_cost_two_statements_not_nine(db: AsyncSession) -> None:
    """`db.get(CandidateProfile)` loaded the profile and its seven eager collections. Every call to
    `match_jobs` made one."""
    skill = _skill(7)
    db.add(skill)
    await db.flush()
    person = await _candidate(db, 4_242, [(skill, "certified")])
    await db.commit()
    # Out of the session, so a lookup that reuses it for free (as `db.get` does) cannot hide what
    # it costs when the profile is not already in memory -- which is most requests.
    db.expunge_all()

    statements, facts = await _count(db, lambda: candidate_facts(db, person.id))

    assert statements <= 2, f"{statements} statements"
    assert facts.years_experience == 2


async def test_a_status_change_scores_one_applicant_not_all_of_them(
    db: AsyncSession, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """Statement counts cannot see this -- scoring is Python -- so ask the scorer what it was
    given."""
    from api.modules.applications import employer_service

    tenant, job, applications = await _vacancy_with_applicants(db, 12, "one")
    seen: list[int] = []
    real = employer_service.score_profiles

    async def spy(db_, job_, ids):  # type: ignore[no-untyped-def]
        seen.append(len(ids))
        return await real(db_, job_, ids)

    monkeypatch.setattr(employer_service, "score_profiles", spy)

    await set_status_and_reload(db, tenant.id, job.slug, applications[0].id, "shortlisted")

    assert seen == [1], f"scored {seen} applicants for one click"
