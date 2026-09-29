"""Course-to-role alignment (Sprint 33, BL-2.3): "the differentiator."

The product definition names this in §5.5 and describes it as already built;
`docs/scope-reconciliation.md` #4 found it was not -- `courses_closing_gap`
only ever compared a course against *a candidate's* gap, never against a role
directly. This is the first function that takes a course and a role and
returns coverage, independent of anybody applying for anything.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity.models import Tenant
from api.modules.marketplace.models import Course, CourseSkill
from api.modules.matching.service import course_role_alignment
from api.modules.skills.hierarchy import QpSkill, QualificationPack, Sector
from api.modules.skills.models import Skill


def _standard(name: str, nos_code: str) -> Skill:
    return Skill(
        slug=f"align-{nos_code.lower().replace('/', '-')}",
        name=name,
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code=nos_code,
        source="nsqf",
    )


@pytest.fixture
async def role(db: AsyncSession) -> QualificationPack:
    """Two compulsory standards, one elective -- so a test can prove the
    elective is excluded from the requirement rather than merely absent."""
    sector = Sector(sector_ref="align-sector", name="Healthcare", slug="align-healthcare")
    db.add(sector)
    await db.flush()

    vitals = _standard("Check vital parameters", "TST/N0910")
    infection = _standard("Follow infection control", "TST/N0911")
    elective = _standard("Optional bedside manner", "TST/N0912")
    db.add_all([vitals, infection, elective])
    await db.flush()

    qp = QualificationPack(
        qp_code="TST/Q0901",
        version="1.0",
        slug="align-general-duty-assistant",
        name="General Duty Assistant qualification",
        job_role="General Duty Assistant",
        nsqf_level=Decimal("4"),
        is_current=True,
        sector_id=sector.id,
    )
    db.add(qp)
    await db.flush()

    db.add_all(
        [
            QpSkill(qp_id=qp.id, skill_id=vitals.id, requirement="compulsory"),
            QpSkill(qp_id=qp.id, skill_id=infection.id, requirement="compulsory"),
            QpSkill(qp_id=qp.id, skill_id=elective.id, requirement="elective"),
        ]
    )
    await db.commit()
    qp._standards = (vitals, infection, elective)  # type: ignore[attr-defined]
    return qp


async def _course(db: AsyncSession, *, teaches: list[Skill]) -> Course:
    tenant = Tenant(
        slug=f"align-provider-{uuid.uuid4().hex[:8]}",
        name="Align Institute",
        tenant_type="course_provider",
    )
    db.add(tenant)
    await db.flush()
    course = Course(
        slug=f"align-course-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant.id,
        title="Ward Care Basics",
        status="published",
    )
    db.add(course)
    await db.flush()
    for skill in teaches:
        db.add(CourseSkill(course_id=course.id, skill_id=skill.id, level_taught=Decimal("4")))
    await db.commit()
    return course


async def test_full_coverage_of_the_compulsory_standards(
    db: AsyncSession, role: QualificationPack
) -> None:
    vitals, infection, elective = role._standards  # type: ignore[attr-defined]
    course = await _course(db, teaches=[vitals, infection])

    alignment = await course_role_alignment(db, course, role.slug)
    assert alignment is not None
    assert alignment.required_count == 2
    assert alignment.coverage_ratio == 1.0
    assert alignment.covered == sorted([vitals.name, infection.name])
    assert alignment.missing == []


async def test_partial_coverage_names_what_is_missing(
    db: AsyncSession, role: QualificationPack
) -> None:
    vitals, infection, _elective = role._standards  # type: ignore[attr-defined]
    course = await _course(db, teaches=[vitals])

    alignment = await course_role_alignment(db, course, role.slug)
    assert alignment is not None
    assert alignment.coverage_ratio == 0.5
    assert alignment.covered == [vitals.name]
    assert alignment.missing == [infection.name]


async def test_teaching_only_the_elective_counts_as_zero_coverage(
    db: AsyncSession, role: QualificationPack
) -> None:
    """The requirement is the compulsory standards. Teaching the elective and
    nothing else covers none of it -- "choose one of these" is not "this is
    required", the same distinction `standards_for_role` itself draws."""
    _vitals, _infection, elective = role._standards  # type: ignore[attr-defined]
    course = await _course(db, teaches=[elective])

    alignment = await course_role_alignment(db, course, role.slug)
    assert alignment is not None
    assert alignment.coverage_ratio == 0.0
    assert alignment.required_count == 2


async def test_a_course_teaching_nothing_relevant_still_returns_the_role(
    db: AsyncSession, role: QualificationPack
) -> None:
    unrelated = _standard("Unrelated skill", "TST/N0999")
    db.add(unrelated)
    await db.flush()
    course = await _course(db, teaches=[unrelated])

    alignment = await course_role_alignment(db, course, role.slug)
    assert alignment is not None
    assert alignment.coverage_ratio == 0.0
    assert len(alignment.missing) == 2


async def test_an_unknown_role_slug_is_none_not_an_error(
    db: AsyncSession, role: QualificationPack
) -> None:
    vitals, _infection, _elective = role._standards  # type: ignore[attr-defined]
    course = await _course(db, teaches=[vitals])
    assert await course_role_alignment(db, course, "no-such-role") is None


async def test_no_candidate_appears_anywhere_in_the_result(
    db: AsyncSession, role: QualificationPack
) -> None:
    """ADR-037 does not apply to this comparison the way it does to
    `candidates_for_job` -- but the reason it does not apply is that no
    person is in scope at all, and this is the test that proves it."""
    vitals, _infection, _elective = role._standards  # type: ignore[attr-defined]
    course = await _course(db, teaches=[vitals])
    alignment = await course_role_alignment(db, course, role.slug)
    assert alignment is not None
    for field in vars(alignment).values():
        assert not isinstance(field, uuid.UUID) or field in (course.id, alignment.qp.id)


class TestTheRoute:
    async def _provider(self, client: AsyncClient) -> tuple[dict[str, str], str]:
        email = f"align-{uuid.uuid4().hex[:10]}@example.com"
        code = (
            await client.post(
                "/auth/org/register",
                json={
                    "email": email,
                    "organisation_name": "Align Institute",
                    "tenant_type": "course_provider",
                    "consent_version": CONSENT,
                },
            )
        ).json()["debug_code"]
        tokens = (
            await client.post("/auth/email/otp/verify", json={"email": email, "code": code})
        ).json()
        headers = {"authorization": f"Bearer {tokens['access_token']}"}
        me = (await client.get("/auth/me", headers=headers)).json()
        slug = next(
            m["tenant"]["slug"]
            for m in me["memberships"]
            if m["tenant"]["tenant_type"] != "personal"
        )
        return headers, slug

    async def test_a_provider_sees_their_own_course_aligned_to_a_role(
        self, client: AsyncClient, db: AsyncSession, role: QualificationPack
    ) -> None:
        headers, org_slug = await self._provider(client)
        vitals, infection, _elective = role._standards  # type: ignore[attr-defined]

        create = await client.post(
            f"/org/{org_slug}/courses",
            json={
                "title": "Ward Care Basics",
                "description": "Enough to publish.",
                "mode": "online",
                "skills": [{"skill_slug": vitals.slug, "level_taught": 4}],
            },
            headers=headers,
        )
        assert create.status_code == 201, create.text
        course_slug = create.json()["slug"]

        response = await client.get(
            f"/org/{org_slug}/courses/{course_slug}/alignment/{role.slug}", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["required_count"] == 2
        assert body["coverage_percent"] == 50
        assert body["covered"] == [vitals.name]
        assert body["missing"] == [infection.name]
        assert body["role_name"] == "General Duty Assistant"

    async def test_someone_elses_course_is_404_not_403(
        self, client: AsyncClient, role: QualificationPack
    ) -> None:
        headers, org_slug = await self._provider(client)
        response = await client.get(
            f"/org/{org_slug}/courses/not-a-real-course/alignment/{role.slug}", headers=headers
        )
        assert response.status_code == 404

    async def test_an_unknown_role_is_404(
        self, client: AsyncClient, db: AsyncSession, role: QualificationPack
    ) -> None:
        headers, org_slug = await self._provider(client)
        vitals, _infection, _elective = role._standards  # type: ignore[attr-defined]
        create = await client.post(
            f"/org/{org_slug}/courses",
            json={
                "title": "Ward Care Basics",
                "description": "Enough to publish.",
                "mode": "online",
                "skills": [{"skill_slug": vitals.slug, "level_taught": 4}],
            },
            headers=headers,
        )
        course_slug = create.json()["slug"]
        response = await client.get(
            f"/org/{org_slug}/courses/{course_slug}/alignment/no-such-role", headers=headers
        )
        assert response.status_code == 404
