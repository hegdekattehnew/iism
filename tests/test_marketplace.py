"""Sprint 3: jobs, courses, and the edges that connect them to the taxonomy."""

from dataclasses import fields

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity import Tenant
from api.modules.marketplace import (
    Course,
    CourseSkill,
    Job,
    JobSkill,
    count_jobs,
    courses_teaching_skill,
    jobs_requiring_skill,
)
from api.modules.marketplace.stats import CorpusStats
from api.modules.skills import Skill


@pytest.fixture
async def seeded(db: AsyncSession) -> dict:
    """Two skills, two employers, two jobs and two courses that overlap on one
    skill — enough to prove the joins in both directions."""
    hygiene = Skill(
        slug="hand-hygiene",
        name_en="Hand hygiene",
        name_hi="हाथ की स्वच्छता",
        skill_type="core",
        nsqf_level=2,
    )
    blood = Skill(
        slug="blood-sample-collection",
        name_en="Blood sample collection",
        name_hi="रक्त नमूना संग्रह",
        skill_type="technical",
        nsqf_level=4,
    )
    db.add_all([hygiene, blood])

    hospital = Tenant(slug="apollo", name="Apollo Care", tenant_type="employer", city="Chennai")
    academy = Tenant(
        slug="academy", name="Health Academy", tenant_type="course_provider", city="Delhi"
    )
    db.add_all([hospital, academy])
    await db.flush()

    gda = Job(
        slug="gda",
        tenant_id=hospital.id,
        title_en="General Duty Assistant",
        title_hi="जनरल ड्यूटी असिस्टेंट",
        description_en="Ward support work.",
        location_state="Tamil Nadu",
        location_district="Chennai",
        employment_type="full_time",
        experience_min_years=0,
        nsqf_level_min=3,
    )
    phleb = Job(
        slug="phleb",
        tenant_id=hospital.id,
        title_en="Phlebotomist",
        description_en="Sample collection.",
        location_state="Telangana",
        employment_type="contract",
        experience_min_years=1,
        nsqf_level_min=4,
    )
    draft = Job(
        slug="draft-job",
        tenant_id=hospital.id,
        title_en="Unpublished role",
        status="draft",
        experience_min_years=0,
    )
    db.add_all([gda, phleb, draft])

    cheap = Course(
        slug="cheap",
        tenant_id=academy.id,
        title_en="Infection basics",
        mode="online",
        language="hi",
        fee_inr=1800,
        nsqf_level=3,
    )
    dear = Course(
        slug="dear",
        tenant_id=academy.id,
        title_en="Phlebotomy Technician",
        mode="offline",
        language="both",
        fee_inr=9000,
        nsqf_level=4,
    )
    db.add_all([cheap, dear])
    await db.flush()

    db.add_all(
        [
            JobSkill(job_id=gda.id, skill_id=hygiene.id, importance=4, is_mandatory=True),
            JobSkill(job_id=phleb.id, skill_id=blood.id, importance=5, is_mandatory=True),
            JobSkill(job_id=phleb.id, skill_id=hygiene.id, importance=2, is_mandatory=False),
            CourseSkill(course_id=cheap.id, skill_id=hygiene.id, level_taught=2),
            CourseSkill(course_id=dear.id, skill_id=blood.id, level_taught=4),
            CourseSkill(course_id=dear.id, skill_id=hygiene.id, level_taught=3),
        ]
    )
    await db.flush()
    return {"db": db, "hygiene": hygiene, "blood": blood, "gda": gda}


# ------------------------------------------------------------------ listing


async def test_listing_excludes_drafts(seeded: dict, client: AsyncClient) -> None:
    """A draft job must never appear in public listings."""
    body = (await client.get("/jobs")).json()
    assert body["total"] == 2
    assert "draft-job" not in [i["slug"] for i in body["items"]]


async def test_count_excludes_drafts(seeded: dict) -> None:
    assert await count_jobs(seeded["db"]) == 2


async def test_job_list_filters_by_skill(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/jobs", params={"skill": "blood-sample-collection"})).json()
    assert [i["slug"] for i in body["items"]] == ["phleb"]


async def test_job_list_filters_by_state(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/jobs", params={"location_state": "Tamil Nadu"})).json()
    assert body["total"] == 1


async def test_job_list_filters_by_employment_type(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/jobs", params={"employment_type": "contract"})).json()
    assert [i["slug"] for i in body["items"]] == ["phleb"]


async def test_course_language_both_satisfies_single_language(
    seeded: dict, client: AsyncClient
) -> None:
    """A bilingual course must show up when a Hindi speaker filters for Hindi."""
    body = (await client.get("/courses", params={"language": "hi"})).json()
    assert {i["slug"] for i in body["items"]} == {"cheap", "dear"}


async def test_course_fee_filter(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/courses", params={"max_fee_inr": 2000})).json()
    assert [i["slug"] for i in body["items"]] == ["cheap"]


async def test_pagination(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/jobs", params={"limit": 1, "offset": 1})).json()
    assert body["total"] == 2 and len(body["items"]) == 1


# ------------------------------------------------------------------- search


async def test_job_search_by_english_title(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/jobs", params={"q": "phlebotomist"})).json()
    assert [i["slug"] for i in body["items"]] == ["phleb"]


async def test_job_search_by_devanagari_title(seeded: dict, client: AsyncClient) -> None:
    """Hindi has no stemmer, so this leans on the ILIKE fallback."""
    body = (await client.get("/jobs", params={"q": "जनरल"})).json()
    assert [i["slug"] for i in body["items"]] == ["gda"]


# ------------------------------------------------------------------- detail


async def test_job_detail_carries_importance_and_mandatory(
    seeded: dict, client: AsyncClient
) -> None:
    body = (await client.get("/jobs/phleb")).json()
    by_slug = {s["skill"]["slug"]: s for s in body["skills"]}
    assert by_slug["blood-sample-collection"]["is_mandatory"] is True
    assert by_slug["blood-sample-collection"]["importance"] == 5
    assert by_slug["hand-hygiene"]["is_mandatory"] is False


async def test_job_detail_includes_the_employer(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/jobs/gda")).json()
    assert body["tenant"]["name"] == "Apollo Care"


async def test_course_detail_carries_level_taught(seeded: dict, client: AsyncClient) -> None:
    body = (await client.get("/courses/dear")).json()
    levels = {s["skill"]["slug"]: s["level_taught"] for s in body["skills"]}
    assert levels["blood-sample-collection"] == 4


async def test_unknown_slugs_404(client: AsyncClient) -> None:
    assert (await client.get("/jobs/nope")).status_code == 404
    assert (await client.get("/courses/nope")).status_code == 404


# ------------------------------------------- the edges: skill <-> marketplace


async def test_jobs_requiring_skill_puts_mandatory_first(seeded: dict) -> None:
    jobs = await jobs_requiring_skill(seeded["db"], seeded["hygiene"].id)
    assert [j.slug for j in jobs] == ["gda", "phleb"]  # gda's is mandatory


async def test_courses_teaching_skill_cheapest_first(seeded: dict) -> None:
    """This cohort is price-sensitive; fee is the usual reason a course is not taken."""
    courses = await courses_teaching_skill(seeded["db"], seeded["hygiene"].id)
    assert [c.slug for c in courses] == ["cheap", "dear"]


async def test_skill_edges_over_http(seeded: dict, client: AsyncClient) -> None:
    jobs = (await client.get("/skills/hand-hygiene/jobs")).json()
    courses = (await client.get("/skills/hand-hygiene/courses")).json()
    assert {j["slug"] for j in jobs} == {"gda", "phleb"}
    assert {c["slug"] for c in courses} == {"cheap", "dear"}


async def test_skill_edges_404_for_unknown_skill(client: AsyncClient) -> None:
    assert (await client.get("/skills/nope/jobs")).status_code == 404
    assert (await client.get("/skills/nope/courses")).status_code == 404


async def test_marketplace_counts(seeded: dict, client: AsyncClient) -> None:
    assert (await client.get("/marketplace/counts")).json() == {"jobs": 2, "courses": 2}


async def test_skills_routes_still_work(seeded: dict, client: AsyncClient) -> None:
    """The new /skills/{slug}/jobs route must not shadow /skills/{slug}."""
    assert (await client.get("/skills/hand-hygiene")).status_code == 200
    assert (await client.get("/skills/search", params={"q": "hand"})).status_code == 200


# ------------------------------------------------------- the landing figures


class TestCorpusStats:
    """`stats.py` backs the only numbers on the landing page, and had no test.

    Its docstring states the rule the tests below hold it to: a marketing figure
    that drifts from reality is worse than no figure. Both exclusions exist so
    that every number a visitor reads is a number they can then go and find.
    """

    async def test_the_figures_need_no_account(self, seeded: dict, client: AsyncClient) -> None:
        """It is the first request a first-time visitor makes."""
        assert (await client.get("/marketplace/stats")).status_code == 200

    async def test_drafts_are_not_counted(self, seeded: dict, client: AsyncClient) -> None:
        """The fixture holds three jobs, one of them a draft. Counting it would
        put a number on the homepage that `/jobs` then contradicts."""
        body = (await client.get("/marketplace/stats")).json()
        assert body["jobs"] == 2
        assert body["courses"] == 2

    async def test_only_nsqf_rows_count_as_standards(
        self, seeded: dict, client: AsyncClient
    ) -> None:
        """`standards` counts `source='nsqf'` alone, exactly as search and browse
        do. The fixture's two skills are `curated` — the Sprint 2 vocabulary
        retired in Sprint 9 — so the headline figure is 0 here, not 2."""
        assert (await client.get("/marketplace/stats")).json()["standards"] == 0

    async def test_every_declared_figure_is_returned(
        self, seeded: dict, client: AsyncClient
    ) -> None:
        """`CorpusStatsOut` and `CorpusStats` are two hand-maintained lists of
        the same ten names; a field added to one and not the other is a
        `ValidationError` at request time, on the landing page."""
        body = (await client.get("/marketplace/stats")).json()
        assert set(body) == {f.name for f in fields(CorpusStats)}
        assert all(isinstance(v, int) for v in body.values())
