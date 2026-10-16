"""Sprint 70 (UI-01, 02, 12, 13, 19): what the first minute of a job seeker has to be true.

A browser cannot show these:

* `/me/matches` says **how many matched in all**, not how long the page is. It returned
  `len(page)` as `total` until Sprint 70, so a screen that said "14 matches" was reading a page of
  twenty (the same defect as a list that prints its length, ADR-079);
* the shared test vectors for the match sentence exist, are well formed and are read by *both*
  clients (a client that stopped reading its copy would pass on cases of its own).
"""

import json
import uuid
from decimal import Decimal
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity.models import Tenant
from api.modules.marketplace.models import CandidateProfile, CandidateSkill, Job, JobSkill
from api.modules.skills.models import Skill

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent


async def _candidate(client: AsyncClient) -> tuple[dict[str, str], uuid.UUID]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    tokens = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    user_id = uuid.UUID((await client.get("/auth/me", headers=headers)).json()["id"])
    return headers, user_id


async def _three_vacancies_one_skill(db: AsyncSession) -> Skill:
    skill = Skill(
        slug="first-minute-skill",
        name="Infection control",
        skill_type="technical",
        nsqf_level=Decimal("3"),
        nos_code="TST/N7001",
        source="nsqf",
    )
    employer = Tenant(slug="first-minute-co", name="First Minute Co", tenant_type="employer")
    db.add_all([skill, employer])
    await db.flush()
    for n in range(3):
        job = Job(
            slug=f"first-minute-job-{n}",
            tenant_id=employer.id,
            title=f"Ward attendant {n}",
            employment_type="full_time",
            nsqf_level_min=Decimal("3"),
            status="published",
        )
        db.add(job)
        await db.flush()
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=5, is_mandatory=True))
    await db.flush()
    return skill


class TestMatchTotal:
    async def test_total_is_how_many_matched_not_how_long_the_page_is(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        skill = await _three_vacancies_one_skill(db)
        headers, user_id = await _candidate(client)
        await client.get("/me/profile", headers=headers)  # creates the profile, lazily
        profile_id = await db.scalar(
            select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
        )
        assert profile_id is not None
        db.add(
            CandidateSkill(
                profile_id=profile_id, skill_id=skill.id, proficiency=4, source="self_declared"
            )
        )
        await db.commit()

        page = (await client.get("/me/matches?limit=2", headers=headers)).json()
        assert len(page["items"]) == 2
        assert page["total"] == 3, "total must be the number of matches, not the page length"

        everything = (await client.get("/me/matches?limit=50", headers=headers)).json()
        assert len(everything["items"]) == 3 and everything["total"] == 3

    async def test_total_agrees_with_the_dashboard_figure(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """Two numbers that mean "how many matches" on two screens must be one number."""
        skill = await _three_vacancies_one_skill(db)
        headers, user_id = await _candidate(client)
        await client.get("/me/profile", headers=headers)
        profile_id = await db.scalar(
            select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
        )
        assert profile_id is not None
        db.add(
            CandidateSkill(
                profile_id=profile_id, skill_id=skill.id, proficiency=4, source="self_declared"
            )
        )
        await db.commit()
        page = (await client.get("/me/matches?limit=1", headers=headers)).json()
        dashboard = (await client.get("/me/dashboard", headers=headers)).json()
        assert page["total"] == dashboard["match_count"] == 3

    async def test_no_skills_is_zero_and_says_so(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        headers, _ = await _candidate(client)
        page = (await client.get("/me/matches", headers=headers)).json()
        assert page["total"] == 0 and page["has_skills"] is False


class TestSharedVectors:
    """Both clients read this file; a test here keeps it honest and found."""

    def test_the_match_summary_cases_exist_and_are_well_formed(self) -> None:
        cases = json.loads((FIXTURES / "match_summary_cases.json").read_text())["cases"]
        assert len(cases) >= 8
        kinds = {c["expect"]["kind"] for c in cases}
        # Every shape the sentence can take has a case that produces it.
        assert kinds == {"all", "some", "none"}
        for c in cases:
            assert {"name", "matched", "missing", "expect"} <= set(c)

    def test_both_clients_read_the_file(self) -> None:
        for test in ("web/src/lib/match-summary.test.ts", "mobile/src/test/match-summary.test.ts"):
            source = (ROOT / test).read_text()
            assert "match_summary_cases.json" in source, f"{test} no longer reads the shared cases"
