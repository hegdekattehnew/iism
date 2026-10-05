"""Who is here and what has been done (Sprint 50.5).

Each figure on the homepage is a claim, and a claim that is easy to inflate is the one a buyer
catches. The cases below are the *exclusions*, because each is the way a number would quietly
become bigger than the truth: browsing creates a profile, every candidate owns a personal
workspace, a withdrawn application and a no-show are not what a visitor imagines.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.applications.models import Application
from api.modules.geography.models import District, State
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import (
    CandidateProfile,
    CandidateSkill,
    Course,
    Job,
)
from api.modules.marketplace.stats import corpus_stats, is_demonstration
from api.modules.skills.models import Skill


async def _figures(db: AsyncSession) -> dict:
    stats = await corpus_stats(db)
    return stats.__dict__


async def _delta(db: AsyncSession, build) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """What changed in each figure when `build` ran. The database holds seed rows, so the
    assertions are about differences, never absolutes."""
    before = await _figures(db)
    await build()
    await db.flush()
    after = await _figures(db)
    return {
        k: after[k] - before[k]
        for k in after
        if isinstance(after[k], int) and after[k] != before[k]
    }


def _skill(n: int = 0) -> Skill:
    return Skill(
        slug=f"figures-skill-{uuid.uuid4().hex[:8]}",
        name=f"Standard {n}",
        skill_type="technical",
        nsqf_level=Decimal("3"),
        nos_code=f"FIG/N{uuid.uuid4().hex[:6]}",
        source="nsqf",
    )


async def _profile(db: AsyncSession, *, skills: list[Skill] | None = None) -> CandidateProfile:
    user = User(phone=f"+9199{uuid.uuid4().int % 100000000:08d}")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(user_id=user.id)
    db.add(profile)
    await db.flush()
    for skill in skills or []:
        db.add(CandidateSkill(profile_id=profile.id, skill_id=skill.id, proficiency=3))
    await db.flush()
    return profile


class TestJobSeekers:
    async def test_a_profile_with_a_declared_standard_is_a_job_seeker(
        self, db: AsyncSession
    ) -> None:
        skill = _skill()
        db.add(skill)
        await db.flush()

        delta = await _delta(db, lambda: _profile(db, skills=[skill]))

        assert delta == {"job_seekers": 1, "profiles": 1}

    async def test_an_empty_profile_is_signed_up_but_not_a_job_seeker(
        self, db: AsyncSession
    ) -> None:
        """`ensure_profile` creates one on a visit, so counting rows would let browsing inflate
        the headline."""
        delta = await _delta(db, lambda: _profile(db))
        assert delta == {"profiles": 1}

    async def test_it_is_the_employer_consoles_figure_too(self, db: AsyncSession) -> None:
        """One definition of a job seeker (`skilled_profile`): two figures that disagreed about
        who counts would be reported as a bug by whoever saw both."""
        from api.modules.matching.employer import candidates_total

        skill = _skill()
        db.add(skill)
        await db.flush()
        await _profile(db, skills=[skill])
        await _profile(db)
        assert (await _figures(db))["job_seekers"] == await candidates_total(db)


class TestOrganisations:
    async def test_a_personal_workspace_is_not_an_employer(self, db: AsyncSession) -> None:
        """Every candidate owns one; counting them would make a business of every job seeker."""
        delta = await _delta(
            db,
            lambda: _add(
                db, Tenant(slug=f"p-{uuid.uuid4().hex[:6]}", name="P", tenant_type="personal")
            ),
        )
        assert delta == {}

    async def test_an_employer_counts_and_is_hiring_only_with_an_open_vacancy(
        self, db: AsyncSession
    ) -> None:
        tenant = Tenant(slug=f"e-{uuid.uuid4().hex[:6]}", name="E", tenant_type="employer")
        db.add(tenant)
        await db.flush()
        assert await _delta(db, lambda: _noop()) == {}

        registered = await _delta(
            db,
            lambda: _add(
                db, Tenant(slug=f"e2-{uuid.uuid4().hex[:6]}", name="E2", tenant_type="employer")
            ),
        )
        assert registered == {"employers": 1}

        hiring = await _delta(db, lambda: _add(db, _job(tenant)))
        assert hiring["employers_hiring"] == 1 and hiring["jobs_open"] == 1

    async def test_a_closed_or_draft_vacancy_does_not_make_an_employer_hiring(
        self, db: AsyncSession
    ) -> None:
        state = State(state_code=9702, name="Closed State", slug="closed-state")
        db.add(state)
        await db.flush()
        district = District(district_code=97021, name="Closed Town", state_id=state.id)
        tenant = _tenant("employer")
        db.add_all([district, tenant])
        await db.flush()
        # Both sit in a real district, so a "districts" figure that counted them would move.
        closed = _job(tenant)
        closed.closed_at = datetime.now(UTC)
        closed.close_reason = "filled"
        closed.district_id = district.id
        draft = _job(tenant)
        draft.status = "draft"
        draft.district_id = district.id

        delta = await _delta(db, lambda: _add(db, closed, draft))

        assert "employers_hiring" not in delta
        assert "districts_with_vacancy" not in delta

    async def test_a_provider_has_a_course_only_when_one_is_published(
        self, db: AsyncSession
    ) -> None:
        tenant = Tenant(slug=f"c-{uuid.uuid4().hex[:6]}", name="C", tenant_type="course_provider")
        db.add(tenant)
        await db.flush()

        draft = await _delta(
            db,
            lambda: _add(
                db,
                Course(
                    slug=f"d-{uuid.uuid4().hex[:6]}",
                    tenant_id=tenant.id,
                    title="Draft",
                    status="draft",
                ),
            ),
        )
        assert "providers_with_course" not in draft

        live = await _delta(
            db,
            lambda: _add(
                db,
                Course(
                    slug=f"l-{uuid.uuid4().hex[:6]}",
                    tenant_id=tenant.id,
                    title="Live",
                    status="published",
                ),
            ),
        )
        assert live["providers_with_course"] == 1 and live["courses"] == 1

    async def test_a_provider_counts_whether_or_not_it_has_a_course(self, db: AsyncSession) -> None:
        delta = await _delta(
            db,
            lambda: _add(
                db,
                Tenant(slug=f"c2-{uuid.uuid4().hex[:6]}", name="C2", tenant_type="course_provider"),
            ),
        )
        assert delta == {"providers": 1}


class TestWork:
    async def _vacancy_with_applicant(
        self, db: AsyncSession, status: str
    ) -> tuple[Job, Application]:
        tenant = _tenant("employer")
        db.add(tenant)
        await db.flush()
        job = _job(tenant)
        db.add(job)
        await db.flush()
        profile = await _profile(db)
        application = Application(job_id=job.id, profile_id=profile.id, status=status)
        return job, application

    @pytest.mark.parametrize(
        "status,counts_as_hire",
        [
            ("applied", False),
            ("shortlisted", False),
            ("rejected", False),
            ("withdrawn", False),
            ("no_show", False),
            ("hired", True),
            ("completed", True),
        ],
    )
    async def test_every_application_counts_and_only_filled_ones_are_hires(
        self, db: AsyncSession, status: str, counts_as_hire: bool
    ) -> None:
        """A withdrawn application is still one the candidate made. A no-show was hired but left
        the seat empty, so it is not a hire to boast of."""
        _job_row, application = await self._vacancy_with_applicant(db, status)

        delta = await _delta(db, lambda: _add(db, application))

        assert delta.get("applications") == 1
        assert delta.get("hires", 0) == (1 if counts_as_hire else 0)


class TestReach:
    async def test_districts_with_a_vacancy_counts_places_not_vacancies(
        self, db: AsyncSession
    ) -> None:
        state = State(state_code=9701, name="Reach State", slug="reach-state")
        db.add(state)
        await db.flush()
        a = District(district_code=97011, name="Reach A", state_id=state.id)
        b = District(district_code=97012, name="Reach B", state_id=state.id)
        db.add_all([a, b])
        await db.flush()
        tenant = _tenant("employer")
        db.add(tenant)
        await db.flush()

        def vacancy(district: District) -> Job:
            job = _job(tenant)
            job.district_id = district.id
            job.state_id = state.id
            return job

        # Two vacancies in A and one in B: two places.
        delta = await _delta(db, lambda: _add(db, vacancy(a), vacancy(a), vacancy(b)))

        assert delta["districts_with_vacancy"] == 2
        assert delta["jobs_open"] == 3

    async def test_the_master_list_is_a_different_figure(self, db: AsyncSession) -> None:
        stats = await corpus_stats(db)
        assert stats.districts >= stats.districts_with_vacancy


class TestTheDemonstrationFlag:
    @staticmethod
    def _settings(monkeypatch, environment: str, database: str) -> None:  # type: ignore[no-untyped-def]
        class Fake:
            database_url = f"postgresql+asyncpg://u:p@h:5432/{database}"

        Fake.environment = environment  # type: ignore[attr-defined]
        monkeypatch.setattr("api.modules.marketplace.stats.get_settings", lambda: Fake())

    @pytest.mark.parametrize("environment", ["development", "test", "staging", "ci"])
    def test_anything_but_production_is_a_demonstration(
        self,
        monkeypatch,
        environment: str,  # type: ignore[no-untyped-def]
    ) -> None:
        self._settings(monkeypatch, environment, "iism")
        assert is_demonstration()

    def test_a_scale_database_is_always_a_demonstration(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Fifty thousand synthetic candidates must never read as traction, even under the
        environment name `production`."""
        self._settings(monkeypatch, "production", "iism_scale")
        assert is_demonstration()

    def test_production_data_is_not_a_demonstration(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        self._settings(monkeypatch, "production", "iism")
        assert not is_demonstration()


class TestOneRoundTrip:
    async def test_the_figures_cost_one_statement(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Eleven counts used to be eleven statements, and the new ones would make it nineteen on
        the page every visitor sees first."""
        statements: list[str] = []

        def count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement)

        connection = (await db.connection()).sync_connection
        assert connection is not None
        event.listen(connection, "before_cursor_execute", count)
        try:
            response = await client.get("/marketplace/stats")
        finally:
            event.remove(connection, "before_cursor_execute", count)

        assert response.status_code == 200
        assert len(statements) == 1, f"{len(statements)} statements"
        body = response.json()
        assert body["demo"] is True  # the suite never runs as production


# --- helpers kept at the bottom so the cases above read as the rule, not the setup


def _tenant(kind: str) -> Tenant:
    return Tenant(slug=f"{kind[:3]}-{uuid.uuid4().hex[:8]}", name=kind, tenant_type=kind)


def _course(tenant: Tenant, status: str) -> Course:
    return Course(
        slug=f"course-{uuid.uuid4().hex[:8]}", tenant_id=tenant.id, title=status, status=status
    )


async def _noop() -> None:
    return None


async def _add(db: AsyncSession, *rows) -> None:  # type: ignore[no-untyped-def]
    db.add_all(rows)
    await db.flush()


def _job(tenant: Tenant) -> Job:
    return Job(
        slug=f"fig-job-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant.id,
        title="Figure vacancy",
        employment_type="full_time",
        status="published",
    )
