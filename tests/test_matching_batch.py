"""One question asked of many candidates (Sprint 50).

`programme_report` used to call `match_jobs` once per enrolled candidate -- about 133 ms
each at 5,000 vacancies, so ten thousand enrolled took twenty-two minutes, and past 32,767
the request failed on a bind-parameter limit. `profiles_with_serious_match` answers the same
question with a handful of queries.

The rule these guard is that it is the **same answer**, not a faster approximation: the old
loop is kept here as the oracle, and every case compares the two.
"""

import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.matching import batch as batch_module
from api.modules.matching import match_jobs, profiles_with_serious_match
from api.modules.matching import service as service_module
from api.modules.matching.scoring import SERIOUS_MATCH_SCORE
from tests.test_retrieval import _candidate, _employer, _job, _random_world, _skill


async def _oracle(db: AsyncSession, profile_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """The loop this replaced, verbatim in meaning."""
    out = set()
    for profile_id in profile_ids:
        scored = await match_jobs(db, profile_id)
        if any(s.result.score >= SERIOUS_MATCH_SCORE for s in scored):
            out.add(profile_id)
    return out


class TestSameAnswerAsTheLoop:
    @pytest.mark.parametrize("seed", [49, 7, 21])
    async def test_it_agrees_on_a_randomised_marketplace(self, db: AsyncSession, seed: int) -> None:
        _jobs, profiles = await _random_world(db, seed=seed)
        ids = [p.id for p in profiles]

        expected = await _oracle(db, ids)
        got = await profiles_with_serious_match(db, ids)

        assert got == expected
        # A world where nobody (or everybody) matches would agree for no reason.
        assert 0 < len(expected) < len(ids), f"seed {seed}: {len(expected)} of {len(ids)}"

    async def test_a_serious_pair_ranked_after_weaker_looking_ones_is_still_found(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The bound ranks on coverage alone, so three vacancies that *look* better (high
        coverage) outrank the one that actually scores: each is held to 55 by a level floor and an
        experience floor the candidate misses. Scoring one pair a round has to walk past them."""
        skills = [_skill(n) for n in range(5)]
        db.add_all(skills)
        await db.flush()
        tenant = await _employer(db)
        for i in range(3):
            await _job(
                db,
                tenant,
                f"looks-better-{i}",
                [(s, 3, False) for s in skills],
                level="10",
                min_years=10,
            )
        strong = await _job(db, tenant, "scores", [(skills[0], 3, False), (skills[4], 3, False)])
        candidate = await _candidate(db, 1, [(s, "certified") for s in skills[:3]], years=0)
        monkeypatch.setattr(batch_module, "ROUND", 1)

        assert strong is not None
        assert await _oracle(db, [candidate.id]) == {candidate.id}
        assert await profiles_with_serious_match(db, [candidate.id]) == {candidate.id}

    async def test_the_retrieval_limit_applies_as_it_does_to_match_jobs(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`match_jobs` scores only its top K by bound. With K = 2 the only serious vacancy
        (ranked fourth) is never seen, so the loop says no -- and so must the batch. A batch
        that ignored K would be answering a different question than the product asks."""
        skills = [_skill(n) for n in range(5)]
        db.add_all(skills)
        await db.flush()
        tenant = await _employer(db)
        for i in range(3):
            await _job(
                db,
                tenant,
                f"looks-better-{i}",
                [(s, 3, False) for s in skills],
                level="10",
                min_years=10,
            )
        await _job(db, tenant, "scores", [(skills[0], 3, False), (skills[4], 3, False)])
        candidate = await _candidate(db, 1, [(s, "certified") for s in skills[:3]], years=0)
        monkeypatch.setattr(service_module, "retrieval_limit", lambda: 2)
        monkeypatch.setattr(batch_module, "retrieval_limit", lambda: 2)

        assert await _oracle(db, [candidate.id]) == set()
        assert await profiles_with_serious_match(db, [candidate.id]) == set()

        monkeypatch.setattr(service_module, "retrieval_limit", lambda: 500)
        monkeypatch.setattr(batch_module, "retrieval_limit", lambda: 500)
        assert await _oracle(db, [candidate.id]) == {candidate.id}
        assert await profiles_with_serious_match(db, [candidate.id]) == {candidate.id}

    async def test_a_candidate_with_nothing_declared_never_matches(self, db: AsyncSession) -> None:
        skill = _skill(0)
        db.add(skill)
        await db.flush()
        tenant = await _employer(db)
        await _job(db, tenant, "open", [(skill, 3, False)])
        empty = await _candidate(db, 1, [])
        assert await profiles_with_serious_match(db, [empty.id]) == set()

    async def test_a_missing_mandatory_standard_is_never_serious(self, db: AsyncSession) -> None:
        """Capped at 45, below the threshold: pruned in the database, and still agrees with
        the scorer."""
        a, b = _skill(0), _skill(1)
        db.add_all([a, b])
        await db.flush()
        tenant = await _employer(db)
        await _job(db, tenant, "gated", [(a, 5, False), (b, 1, True)])
        person = await _candidate(db, 1, [(a, "certified")])
        assert await _oracle(db, [person.id]) == set()
        assert await profiles_with_serious_match(db, [person.id]) == set()

    async def test_the_answer_does_not_depend_on_how_the_candidates_are_chunked(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _jobs, profiles = await _random_world(db, seed=49)
        ids = [p.id for p in profiles]
        whole = await profiles_with_serious_match(db, ids)

        monkeypatch.setattr(batch_module, "CHUNK", 3)
        assert await profiles_with_serious_match(db, ids) == whole

    async def test_a_candidate_listed_twice_counts_once(self, db: AsyncSession) -> None:
        skill = _skill(0)
        db.add(skill)
        await db.flush()
        tenant = await _employer(db)
        await _job(db, tenant, "open", [(skill, 3, False)])
        person = await _candidate(db, 1, [(skill, "certified")])
        assert await profiles_with_serious_match(db, [person.id, person.id]) == {person.id}


class TestTheCostDoesNotGrowWithTheProgramme:
    async def test_statements_do_not_depend_on_how_many_are_enrolled(
        self, db: AsyncSession
    ) -> None:
        """Ten candidates or forty, each confirmed in the first round: the same number of
        statements. The loop it replaced issued seventeen per person."""
        skill = _skill(0)
        db.add(skill)
        await db.flush()
        tenant = await _employer(db)
        await _job(db, tenant, "open", [(skill, 3, False)])
        people = [await _candidate(db, n, [(skill, "certified")]) for n in range(40)]

        statements: list[str] = []

        def count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement)

        async def measure(ids: list[uuid.UUID]) -> tuple[int, set[uuid.UUID]]:
            statements.clear()
            connection = (await db.connection()).sync_connection
            assert connection is not None
            event.listen(connection, "before_cursor_execute", count)
            try:
                found = await profiles_with_serious_match(db, ids)
            finally:
                event.remove(connection, "before_cursor_execute", count)
            return len(statements), found

        few, found_few = await measure([p.id for p in people[:10]])
        many, found_many = await measure([p.id for p in people])

        assert few == many, f"{few} statements for 10, {many} for 40"
        assert found_few == {p.id for p in people[:10]}
        assert found_many == {p.id for p in people}
        assert many < 20
