"""The employer overview's three counts, from the database (Sprint 50).

`job_pools` used to score every candidate sharing a standard with every vacancy, loading each
as a full profile, to read three integers off the results. At 50,000 candidates that was 20
seconds for an employer with 54 vacancies. `ready` and `nearly` are defined by the number of
mandatory standards missing -- which the retrieval SQL already has -- so the scorer adds nothing
to them. These hold the counts to what the scorer says, pair by pair.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.matching import employer as employer_module
from api.modules.matching.employer import _candidates_for_jobs, candidates_total, job_pools
from tests.test_retrieval import _candidate, _employer, _job, _random_world, _skill


@pytest.mark.parametrize("seed", [49, 7, 21])
async def test_the_counts_equal_what_scoring_every_sharer_says(db: AsyncSession, seed: int) -> None:
    jobs, profiles = await _random_world(db, seed=seed)
    tenant_id = jobs[0].tenant_id

    pools = {p.job.id: p for p in await job_pools(db, tenant_id)}
    scored = await _candidates_for_jobs(db, jobs)

    checked = 0
    for job in jobs:
        results = [s.result for s in scored[job.id]]
        expected = (
            len(results),
            sum(1 for r in results if r.missing_mandatory == 0),
            sum(1 for r in results if r.missing_mandatory == 1),
        )
        got = (pools[job.id].pool, pools[job.id].ready, pools[job.id].nearly)
        assert got == expected, f"{job.slug}: {got} != {expected}"
        checked += expected[0]
    assert checked > 40, "the world is too thin to say anything"
    assert any(p.ready for p in pools.values()) and any(p.nearly for p in pools.values())


async def test_the_counts_are_totals_not_the_first_k(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pool used to be counted over the K candidates retrieved, so a vacancy with more
    sharers than that undercounted. Counted in the database it cannot."""
    skill = _skill(0)
    gate = _skill(1)
    db.add_all([skill, gate])
    await db.flush()
    tenant = await _employer(db)
    await _job(db, tenant, "crowded", [(skill, 3, False), (gate, 3, True)])
    for n in range(12):
        await _candidate(db, n, [(skill, "certified")] + ([(gate, "certified")] if n < 5 else []))
    monkeypatch.setattr(employer_module, "retrieval_limit", lambda: 3)

    (pool,) = await job_pools(db, tenant.id)

    assert (pool.pool, pool.ready, pool.nearly) == (12, 5, 7)


async def test_a_vacancy_nobody_shares_a_standard_with_counts_zero(db: AsyncSession) -> None:
    skill = _skill(0)
    db.add(skill)
    await db.flush()
    tenant = await _employer(db)
    await _job(db, tenant, "lonely", [(skill, 3, False)])
    (pool,) = await job_pools(db, tenant.id)
    assert (pool.pool, pool.ready, pool.nearly) == (0, 0, 0)


async def test_the_candidate_total_counts_profiles_with_a_declared_standard(
    db: AsyncSession,
) -> None:
    before = await candidates_total(db)
    skill = _skill(0)
    db.add(skill)
    await db.flush()
    await _candidate(db, 1, [(skill, "certified")])
    await _candidate(db, 2, [(skill, "assessed")])
    await _candidate(
        db, 3, []
    )  # a profile with nothing declared is not a candidate anybody could be shown
    assert await candidates_total(db) == before + 2
