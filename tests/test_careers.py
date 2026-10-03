"""`GET /me/careers` (Sprint 42, ADR-049): the roles that build on a candidate's own.

What is worth proving at this layer: the person is never put on a ladder they did
not start (a guess is exact-or-alias or nothing, and says it is a guess), the fit
is the real scorer's, nothing about them leaves in the measurement, and a role
with no step above it is not confused with a role that does not exist.
"""

import itertools
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import Tenant
from api.modules.identity.models import User
from api.modules.marketplace.models import (
    CandidateExperience,
    CandidatePreferredRole,
    CandidateProfile,
    Course,
    CourseSkill,
)
from api.modules.skills.hierarchy import (
    QpEntryRoute,
    QpSkill,
    QualificationPack,
    RoleAlias,
    Sector,
)
from api.modules.skills.models import Skill

_n = itertools.count(1)


async def _skill(db: AsyncSession, name: str) -> Skill:
    i = next(_n)
    skill = Skill(
        slug=f"car-skill-{i}",
        name=name,
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code=f"CAR/N{i:04d}",
        source="nsqf",
    )
    db.add(skill)
    await db.flush()
    return skill


async def _pack(
    db: AsyncSession,
    sector: Sector,
    role: str,
    level: str,
    standards: list[Skill],
    *,
    routes: list[tuple[str, str]] = (),  # type: ignore[assignment]
    current: bool = True,
) -> QualificationPack:
    i = next(_n)
    pack = QualificationPack(
        qp_code=f"CAR/Q{i:04d}",
        version="1.0",
        slug=f"car-pack-{i}",
        name=f"{role} qualification",
        job_role=role,
        nsqf_level=Decimal(level),
        is_current=current,
        sector_id=sector.id,
    )
    db.add(pack)
    await db.flush()
    for skill in standards:
        db.add(
            QpSkill(
                qp_id=pack.id, skill_id=skill.id, requirement="compulsory", nsqf_level=Decimal("4")
            )
        )
    for ordinal, (education, years) in enumerate(routes):
        db.add(
            QpEntryRoute(
                qp_id=pack.id,
                ordinal=ordinal,
                education_desc=education,
                experience_years=Decimal(years),
            )
        )
    await db.flush()
    return pack


async def _candidate(client: AsyncClient, skills: list[Skill]) -> tuple[dict[str, str], str]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    headers = {"authorization": f"Bearer {body['access_token']}"}
    for skill in skills:
        added = await client.post(
            "/me/profile/skills", headers=headers, json={"skill_slug": skill.slug, "proficiency": 4}
        )
        assert added.status_code in (200, 201), added.text
    return headers, "+91" + phone


async def _profile(db: AsyncSession, phone: str) -> CandidateProfile:
    return (
        await db.scalars(
            select(CandidateProfile)
            .join(User, User.id == CandidateProfile.user_id)
            .where(User.phone == phone)
        )
    ).one()


@pytest.fixture
async def world(client: AsyncClient, db: AsyncSession) -> dict:
    """Ward Assistant (3) -> Senior Ward Assistant (4), which adds two standards a
    course teaches one of. A third role has no step above it."""
    sector = Sector(sector_ref="car-sec", name="Healthcare", slug="car-sec")
    db.add(sector)
    await db.flush()
    a, b, c, d = [await _skill(db, n) for n in ("Unit A", "Unit B", "Unit C", "Unit D")]
    anchor = await _pack(db, sector, "Ward Assistant", "3", [a, b])
    step = await _pack(
        db,
        sector,
        "Senior Ward Assistant",
        "4",
        [a, c, d],
        routes=[("Grade 12", "2.0"), ("Diploma", "1.0")],
    )
    top = await _pack(db, sector, "Ward Director", "9", [d])

    provider = Tenant(slug="car-provider", name="Care Institute", tenant_type="course_provider")
    db.add(provider)
    await db.flush()
    course = Course(
        slug="car-course", tenant_id=provider.id, title="Wound Care", status="published"
    )
    db.add(course)
    await db.flush()
    db.add(CourseSkill(course_id=course.id, skill_id=c.id, level_taught=Decimal("4")))
    await db.commit()
    return {"sector": sector, "skills": (a, b, c, d), "anchor": anchor, "step": step, "top": top}


async def test_signed_out_is_401(client: AsyncClient) -> None:
    assert (await client.get("/me/careers")).status_code == 401


async def test_an_organisation_only_account_is_refused(client: AsyncClient) -> None:
    address = f"car-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Org Only",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.get("/me/careers", headers=headers)).status_code == 403


async def test_a_chosen_role_shows_the_fit_the_gap_the_courses_and_the_way_in(
    client: AsyncClient, world: dict
) -> None:
    a, b, c, d = world["skills"]
    headers, _ = await _candidate(client, [a, b])

    body = (
        await client.get("/me/careers", headers=headers, params={"role": world["anchor"].slug})
    ).json()

    assert body["anchor"]["job_role"] == "Ward Assistant"
    assert (body["anchor_source"], body["needs_choice"], body["has_skills"]) == (
        "chosen",
        False,
        True,
    )
    assert [s["role"]["job_role"] for s in body["steps"]] == ["Senior Ward Assistant"]
    step = body["steps"][0]
    assert step["basis"] == {
        "shared_standards": 1,
        "compulsory_count": 3,
        "same_occupation": False,
        "shared_nco": False,
    }
    assert {m["name"] for m in step["missing"]} == {"Unit C", "Unit D"}
    assert step["missing_mandatory"] == 2
    assert step["score"] <= 45
    assert [c["title"] for c in step["courses"]] == ["Wound Care"]
    assert step["entry"]["lowest_experience_years"] == 1.0
    assert step["entry"]["education_options"] == ["Diploma", "Grade 12"]


async def test_the_fit_is_the_real_scorers_so_holding_everything_is_a_full_match(
    client: AsyncClient, world: dict
) -> None:
    a, b, c, d = world["skills"]
    headers, _ = await _candidate(client, [a, c, d])

    step = (
        await client.get("/me/careers", headers=headers, params={"role": world["anchor"].slug})
    ).json()["steps"][0]

    assert step["missing"] == [] and step["coverage"] == 1.0
    assert step["courses"] == []


async def test_a_candidate_with_no_skills_still_sees_the_ladder_and_is_told(
    client: AsyncClient, world: dict
) -> None:
    headers, _ = await _candidate(client, [])

    body = (
        await client.get("/me/careers", headers=headers, params={"role": world["anchor"].slug})
    ).json()

    assert body["has_skills"] is False
    assert body["steps"][0]["score"] == 0
    assert len(body["steps"][0]["missing"]) == 3


async def test_with_no_role_and_nothing_to_go_on_the_person_is_asked(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, _ = await _candidate(client, [world["skills"][0]])

    body = (await client.get("/me/careers", headers=headers)).json()

    assert body["anchor"] is None
    assert (body["anchor_source"], body["needs_choice"], body["steps"]) == ("none", True, [])
    # Nothing was shown, so nothing is measured.
    assert (
        await db.scalars(
            select(AnalyticsEvent).where(AnalyticsEvent.name == "career_ladder_viewed")
        )
    ).all() == []


async def test_a_current_job_title_that_is_the_role_exactly_is_a_flagged_guess(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, phone = await _candidate(client, [world["skills"][0]])
    profile = await _profile(db, phone)
    db.add(
        CandidateExperience(
            profile_id=profile.id,
            employer_name="City Hospital",
            role_title="  ward   ASSISTANT ",
            started_on=date(2024, 1, 1),
            is_current=True,
        )
    )
    await db.commit()

    body = (await client.get("/me/careers", headers=headers)).json()

    assert body["anchor"]["slug"] == world["anchor"].slug
    assert body["anchor_source"] == "guessed"
    assert body["steps"]


async def test_an_alias_that_is_the_title_resolves(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    db.add(RoleAlias(surface_form="ward boy", job_role="Ward Assistant"))
    headers, phone = await _candidate(client, [world["skills"][0]])
    profile = await _profile(db, phone)
    db.add(CandidatePreferredRole(profile_id=profile.id, title="Ward Boy"))
    await db.commit()

    body = (await client.get("/me/careers", headers=headers)).json()

    assert (body["anchor"]["job_role"], body["anchor_source"]) == ("Ward Assistant", "guessed")


@pytest.mark.parametrize("title", ["Ward Assist", "Assistant", "Ward Assistent", "Ward"])
async def test_a_partial_or_fuzzy_title_is_not_trusted(
    client: AsyncClient, db: AsyncSession, world: dict, title: str
) -> None:
    """A prefix, a substring and a typo each find the role in search. None of them
    is the person saying it, and a ladder from the wrong role is about somebody else."""
    headers, phone = await _candidate(client, [world["skills"][0]])
    profile = await _profile(db, phone)
    db.add(CandidatePreferredRole(profile_id=profile.id, title=title))
    await db.commit()

    body = (await client.get("/me/careers", headers=headers)).json()

    assert (body["anchor"], body["needs_choice"]) == (None, True)


async def test_a_chosen_role_beats_a_guess(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, phone = await _candidate(client, [world["skills"][0]])
    profile = await _profile(db, phone)
    db.add(CandidatePreferredRole(profile_id=profile.id, title="Ward Assistant"))
    await db.commit()

    body = (
        await client.get("/me/careers", headers=headers, params={"role": world["step"].slug})
    ).json()

    assert (body["anchor"]["job_role"], body["anchor_source"]) == (
        "Senior Ward Assistant",
        "chosen",
    )


async def test_a_role_with_nothing_above_it_is_empty_not_missing(
    client: AsyncClient, world: dict
) -> None:
    headers, _ = await _candidate(client, [world["skills"][0]])

    response = await client.get("/me/careers", headers=headers, params={"role": world["top"].slug})

    assert response.status_code == 200
    body = response.json()
    assert body["steps"] == [] and body["needs_choice"] is False
    assert body["anchor"]["job_role"] == "Ward Director"


async def test_an_unknown_or_retired_role_is_404(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    retired = await _pack(
        db, world["sector"], "Retired Role", "3", [world["skills"][0]], current=False
    )
    await db.commit()
    headers, _ = await _candidate(client, [world["skills"][0]])

    for slug in ("no-such-role", retired.slug):
        response = await client.get("/me/careers", headers=headers, params={"role": slug})
        assert response.status_code == 404, slug


async def test_the_measurement_names_the_role_and_counts_and_nobody_else(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    a, b, c, d = world["skills"]
    headers, phone = await _candidate(client, [a, b])

    await client.get("/me/careers", headers=headers, params={"role": world["anchor"].slug})

    event_row = (
        await db.scalars(
            select(AnalyticsEvent).where(AnalyticsEvent.name == "career_ladder_viewed")
        )
    ).one()
    assert event_row.subject_type == "qualification"
    assert event_row.subject_id == world["anchor"].id
    assert event_row.payload == {"steps": 1, "guessed": False}
    # No standard, no name, no phone: a skill list describes a person.
    flat = str(event_row.payload) + str(event_row.subject_id)
    assert not any(word in flat for word in ("Unit", phone[-6:]))


async def test_a_guess_is_recorded_as_one(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, phone = await _candidate(client, [world["skills"][0]])
    profile = await _profile(db, phone)
    db.add(CandidatePreferredRole(profile_id=profile.id, title="Ward Assistant"))
    await db.commit()

    await client.get("/me/careers", headers=headers)

    row = (
        await db.scalars(
            select(AnalyticsEvent).where(AnalyticsEvent.name == "career_ladder_viewed")
        )
    ).one()
    assert row.payload["guessed"] is True


async def test_the_cost_is_linear_in_the_steps_shown_and_nothing_else(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    """Scoring batches; the course lookup (`courses_closing_gap`, six statements)
    runs once per step shown, and that is the whole of the growth. Eight steps is
    the cap, so the ceiling is a fixed number, not something a busy catalogue or a
    long profile can raise."""
    a, b, c, d = world["skills"]
    headers, _ = await _candidate(client, [a, b])

    async def statements() -> int:
        seen: list[str] = []

        def count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
            seen.append(statement)

        connection = (await db.connection()).sync_connection
        event.listen(connection, "before_cursor_execute", count)
        try:
            await client.get("/me/careers", headers=headers, params={"role": world["anchor"].slug})
        finally:
            event.remove(connection, "before_cursor_execute", count)
        return len(seen)

    one = await statements()
    for i in range(3):
        await _pack(db, world["sector"], f"Extra Step {i}", "4", [a, c])
    await db.commit()
    four = await statements()

    per_step = (four - one) / 3
    assert per_step <= 6, f"{per_step} statements per extra step ({one} -> {four})"
