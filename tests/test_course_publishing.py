"""Sprint 14: a training provider can finally do something.

Before this, a `course_provider` tenant could be created and could edit its own
profile, and that was the whole of it — there was no write path for `Course` or
`CourseSkill` anywhere in `api/`. It was handed an employer's workspace, whose
primary button returned 403 into a UI that swallowed the error.

These tests exist mostly to keep the two publishing surfaces from drifting into
each other. They share a shape and not a schema, and the differences are the
part worth guarding.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity import Tenant
from api.modules.skills.models import Skill


def _email() -> str:
    return f"provider-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"


@pytest.fixture
async def taught_skill(db: AsyncSession) -> str:
    skill = Skill(
        slug="sterile-technique-tst-n0101",
        name_en="Apply sterile technique",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N0101",
        source="nsqf",
    )
    db.add(skill)
    await db.commit()
    return skill.slug


@pytest.fixture
async def second_taught_skill(db: AsyncSession) -> str:
    skill = Skill(
        slug="waste-segregation-tst-n0102",
        name_en="Segregate biomedical waste",
        skill_type="technical",
        nsqf_level=Decimal("3"),
        nos_code="TST/N0102",
        source="nsqf",
    )
    db.add(skill)
    await db.commit()
    return skill.slug


async def _provider(client: AsyncClient, db: AsyncSession, name: str) -> tuple[dict[str, str], str]:
    """Register an organisation and make it a training provider.

    Registration still mints `employer`; the type-aware signup path is Part 3 of
    this sprint. Flipping the row here keeps this suite testing publishing
    rather than registration.
    """
    address = _email()
    requested = await client.post(
        "/auth/org/register",
        json={
            "email": address,
            "organisation_name": name,
            "tenant_type": "employer",
            "consent_version": CONSENT,
        },
    )
    code = requested.json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}

    me = (await client.get("/auth/me", headers=headers)).json()
    slug = next(m["tenant"]["slug"] for m in me["memberships"])
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
    assert tenant is not None
    tenant.tenant_type = "course_provider"
    await db.commit()
    return headers, slug


async def _employer(client: AsyncClient, name: str) -> tuple[dict[str, str], str]:
    """Register an ordinary employer. The mirror of `_provider`."""
    address = _email()
    requested = await client.post(
        "/auth/org/register",
        json={
            "email": address,
            "organisation_name": name,
            "tenant_type": "employer",
            "consent_version": CONSENT,
        },
    )
    code = requested.json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/auth/me", headers=headers)).json()
    return headers, me["memberships"][0]["tenant"]["slug"]


class TestCoursePublishing:
    async def test_a_provider_can_publish_a_course(
        self, client: AsyncClient, db: AsyncSession, taught_skill: str
    ) -> None:
        headers, slug = await _provider(client, db, "Sterile Skills Academy")

        created = await client.post(
            f"/org/{slug}/courses",
            headers=headers,
            json={
                "title_en": "Sterile Technique for Ward Staff",
                "mode": "hybrid",
                "language": "both",
                "duration_hours": 60,
                "fee_inr": 4500,
                "nsqf_level": 4,
                "skills": [{"skill_slug": taught_skill, "level_taught": 4}],
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "draft"

        course_slug = created.json()["slug"]
        published = await client.post(f"/org/{slug}/courses/{course_slug}/publish", headers=headers)
        assert published.json()["status"] == "published"

        listed = (await client.get("/courses", params={"limit": 100})).json()
        assert course_slug in [c["slug"] for c in listed["items"]]

    async def test_a_new_course_is_a_draft_and_invisible_to_candidates(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`Course.status` defaults to "published" at the model level, and the
        seed sets it deliberately. A form must not."""
        headers, slug = await _provider(client, db, "Draft Academy")
        created = await client.post(
            f"/org/{slug}/courses",
            headers=headers,
            json={"title_en": "Quietly Drafted Course", "skills": []},
        )

        public = (await client.get("/courses", params={"limit": 100})).json()
        assert created.json()["slug"] not in [c["slug"] for c in public["items"]]

    async def test_publishing_a_course_teaching_nothing_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`courses_closing_gap` inner-joins `CourseSkill`, so a course teaching
        nothing can never be recommended — it would be published and
        permanently unreachable."""
        headers, slug = await _provider(client, db, "Empty Syllabus Academy")
        course = (
            await client.post(
                f"/org/{slug}/courses",
                headers=headers,
                json={"title_en": "Teaches Nothing", "skills": []},
            )
        ).json()

        refused = await client.post(
            f"/org/{slug}/courses/{course['slug']}/publish", headers=headers
        )
        assert refused.status_code == 422

    async def test_duplicate_standards_collapse_on_the_highest_level(
        self, client: AsyncClient, db: AsyncSession, taught_skill: str
    ) -> None:
        """The seed's own rule, and the opposite of a job's: a course covering a
        standard to level 4 in one module and level 3 in another does take the
        learner to 4."""
        headers, slug = await _provider(client, db, "Collapsing Academy")
        created = await client.post(
            f"/org/{slug}/courses",
            headers=headers,
            json={
                "title_en": "Two Modules, One Standard",
                "skills": [
                    {"skill_slug": taught_skill, "level_taught": 3},
                    {"skill_slug": taught_skill, "level_taught": 4},
                ],
            },
        )
        skills = created.json()["skills"]
        assert len(skills) == 1
        assert skills[0]["level_taught"] == 4

    async def test_editing_replaces_the_syllabus(
        self, client: AsyncClient, db: AsyncSession, taught_skill: str, second_taught_skill: str
    ) -> None:
        headers, slug = await _provider(client, db, "Rewriting Academy")
        course = (
            await client.post(
                f"/org/{slug}/courses",
                headers=headers,
                json={
                    "title_en": "Rewritten Syllabus",
                    "skills": [{"skill_slug": taught_skill, "level_taught": 3}],
                },
            )
        ).json()

        updated = await client.put(
            f"/org/{slug}/courses/{course['slug']}",
            headers=headers,
            json={
                "title_en": "Rewritten Syllabus",
                "skills": [{"skill_slug": second_taught_skill, "level_taught": 4}],
            },
        )
        assert [s["skill"]["slug"] for s in updated.json()["skills"]] == [second_taught_skill]

    async def test_the_slug_survives_a_title_change(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _provider(client, db, "Stable Academy")
        course = (
            await client.post(
                f"/org/{slug}/courses",
                headers=headers,
                json={"title_en": "Original Course Title", "skills": []},
            )
        ).json()

        updated = await client.put(
            f"/org/{slug}/courses/{course['slug']}",
            headers=headers,
            json={"title_en": "Completely Different Title", "skills": []},
        )
        assert updated.json()["slug"] == course["slug"]


class TestSharedValidation:
    """`listings.resolve_standards` is the rule both surfaces apply.

    It had **no test in either copy** before Sprint 15, which is how a
    duplicated rule rots: nothing fails when one side drifts. ADR-026 requires
    seeded and self-serve inventory to pass the same validation, so these assert
    the shared path from both directions.
    """

    @pytest.fixture
    async def retired_skill(self, db: AsyncSession) -> str:
        """One of the 52 Sprint-2 skills, retired in Sprint 9. Kept in the table
        because profiles reference it; excluded from matching."""
        skill = Skill(
            slug="hand-hygiene-legacy",
            name_en="Hand hygiene",
            skill_type="core",
            nsqf_level=Decimal("2"),
            source="legacy",
        )
        db.add(skill)
        await db.commit()
        return skill.slug

    async def test_a_course_cannot_teach_a_retired_standard(
        self, client: AsyncClient, db: AsyncSession, retired_skill: str
    ) -> None:
        """Matching compares at concept level and excludes `legacy` rows, so a
        listing anchored to one would be published and permanently unmatchable."""
        headers, slug = await _provider(client, db, "Retired Standard Academy")
        refused = await client.post(
            f"/org/{slug}/courses",
            headers=headers,
            json={
                "title_en": "Teaches Something Retired",
                "skills": [{"skill_slug": retired_skill, "level_taught": 2}],
            },
        )
        assert refused.status_code == 422
        assert "taught" in refused.json()["detail"]
        assert retired_skill in refused.json()["detail"]

    async def test_a_job_cannot_require_a_retired_standard(
        self, client: AsyncClient, retired_skill: str
    ) -> None:
        """The same rule, the other surface, the other verb."""
        headers, slug = await _employer(client, "Retired Standard Clinic")
        refused = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={
                "title_en": "Requires Something Retired",
                "skills": [{"skill_slug": retired_skill, "importance": 3}],
            },
        )
        assert refused.status_code == 422
        assert "required" in refused.json()["detail"]

    async def test_an_unknown_standard_is_named_in_the_refusal(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _provider(client, db, "Typo Academy")
        refused = await client.post(
            f"/org/{slug}/courses",
            headers=headers,
            json={"title_en": "Mistyped", "skills": [{"skill_slug": "no-such-standard"}]},
        )
        assert refused.status_code == 422
        assert "no-such-standard" in refused.json()["detail"]


class TestTheTwoSurfacesStayApart:
    """Membership answers *may this person act here*, never *is this the right
    kind of organisation*. Both directions need the second question asked."""

    async def test_a_provider_cannot_post_a_vacancy(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _provider(client, db, "Not An Employer Academy")
        refused = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={"title_en": "Vacancy from a training provider", "skills": []},
        )
        assert refused.status_code == 403

    async def test_every_write_is_guarded_in_both_directions(
        self, client: AsyncClient, db: AsyncSession, taught_skill: str
    ) -> None:
        """The gap this test exists for: create and publish were guarded and
        **update and unpublish were not**, in either module, while `CLAUDE.md`
        asserted the check ran on every publishing write. Nothing exercised the
        update path with the wrong tenant type, so nothing noticed.

        The guard now travels with the permission in the route's dependency
        rather than being a call each handler must remember, and this walks the
        whole surface rather than sampling it.
        """
        headers, slug = await _provider(client, db, "Every Write Academy")

        # A provider against the vacancy surface: every write, refused.
        job_body = {"title_en": "Not a provider's business", "skills": []}
        assert (
            await client.post(f"/org/{slug}/jobs", headers=headers, json=job_body)
        ).status_code == 403
        assert (
            await client.put(f"/org/{slug}/jobs/anything", headers=headers, json=job_body)
        ).status_code == 403
        assert (
            await client.post(f"/org/{slug}/jobs/anything/publish", headers=headers)
        ).status_code == 403
        assert (
            await client.post(f"/org/{slug}/jobs/anything/unpublish", headers=headers)
        ).status_code == 403
        assert (
            await client.delete(f"/org/{slug}/jobs/anything", headers=headers)
        ).status_code == 403

    async def test_an_employer_is_refused_every_course_write(self, client: AsyncClient) -> None:
        """The mirror. A guard that holds in one direction only is not a guard."""
        headers, slug = await _employer(client, "Every Write Clinic")

        body = {"title_en": "Not an employer's business", "skills": []}
        assert (
            await client.post(f"/org/{slug}/courses", headers=headers, json=body)
        ).status_code == 403
        assert (
            await client.put(f"/org/{slug}/courses/anything", headers=headers, json=body)
        ).status_code == 403
        assert (
            await client.post(f"/org/{slug}/courses/anything/publish", headers=headers)
        ).status_code == 403
        assert (
            await client.post(f"/org/{slug}/courses/anything/unpublish", headers=headers)
        ).status_code == 403
        assert (
            await client.delete(f"/org/{slug}/courses/anything", headers=headers)
        ).status_code == 403

    async def test_a_provider_cannot_read_the_candidate_shortlist(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """It used to answer 200 with two empty arrays and `candidates_total`,
        which has no tenant filter — so the one number on the screen was a
        global count of every candidate on the platform, presented as a pool the
        provider had access to."""
        headers, slug = await _provider(client, db, "Curious Academy")

        assert (await client.get(f"/org/{slug}/candidates", headers=headers)).status_code == 403
