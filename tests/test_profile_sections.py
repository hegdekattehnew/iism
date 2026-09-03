"""Sprint 5: the enriched candidate profile.

Covers the repeating sections, the completeness meter, and the boundaries that
matter -- partial saves, route shadowing and cross-user isolation.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills import Skill


async def _auth(client: AsyncClient) -> dict[str, str]:
    phone = "9" + uuid.uuid4().int.__str__()[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (await client.post("/auth/otp/verify", json={"phone": phone, "code": code})).json()
    return {"authorization": f"Bearer {body['access_token']}"}


@pytest.fixture
async def headers(client: AsyncClient) -> dict[str, str]:
    return await _auth(client)


EXPERIENCE = {
    "employer_name": "Sunrise Hospital",
    "role_title": "Ward Attendant",
    "started_on": "2023-04-01",
    "is_current": True,
}
EDUCATION = {"qualification": "Class 12", "year_completed": 2022}
LANGUAGE = {"language": "Hindi", "proficiency": "native"}


# --------------------------------------------------------------- core fields


async def test_new_profile_is_zero_percent_complete(client: AsyncClient, headers: dict) -> None:
    body = (await client.get("/me/profile", headers=headers)).json()
    assert body["completeness"]["percent"] == 0
    assert "preferred_roles" in body["completeness"]["missing"]


async def test_full_name_is_stored_on_the_user_not_the_profile(
    client: AsyncClient, headers: dict
) -> None:
    """full_name lives on the identity side; the profile endpoint proxies it."""
    await client.put("/me/profile", headers=headers, json={"full_name": "Priya Sharma"})
    assert (await client.get("/auth/me", headers=headers)).json()["full_name"] == "Priya Sharma"
    assert (await client.get("/me/profile", headers=headers)).json()["full_name"] == "Priya Sharma"


async def test_partial_update_does_not_blank_other_fields(
    client: AsyncClient, headers: dict
) -> None:
    """Sections save independently, so a three-field payload must not null the
    fifteen it does not mention."""
    await client.put(
        "/me/profile",
        headers=headers,
        json={
            "full_name": "Priya",
            "location_district": "Hyderabad",
            "willing_to_relocate": True,
            "years_experience": 3,
        },
    )
    body = (
        await client.put("/me/profile", headers=headers, json={"headline": "Phlebotomist"})
    ).json()
    assert body["headline"] == "Phlebotomist"
    assert body["location_district"] == "Hyderabad"
    assert body["willing_to_relocate"] is True
    assert body["years_experience"] == 3
    assert body["full_name"] == "Priya"


async def test_salary_range_is_rejected_when_inverted(client: AsyncClient, headers: dict) -> None:
    res = await client.put(
        "/me/profile",
        headers=headers,
        json={"expected_salary_min_inr": 300000, "expected_salary_max_inr": 100000},
    )
    assert res.status_code == 422


async def test_gender_is_optional_and_constrained(client: AsyncClient, headers: dict) -> None:
    """Personal data under DPDP: optional, and 'prefer not to say' is a real
    answer rather than an absence."""
    ok = await client.put("/me/profile", headers=headers, json={"gender": "prefer_not_to_say"})
    assert ok.status_code == 200
    bad = await client.put("/me/profile", headers=headers, json={"gender": "unknown"})
    assert bad.status_code == 422


# ---------------------------------------------------------- child collections


@pytest.mark.parametrize(
    ("collection", "payload"),
    [
        ("experiences", EXPERIENCE),
        ("educations", EDUCATION),
        ("certifications", {"name": "Phlebotomy Technician", "issuing_body": "HSSC"}),
        ("languages", LANGUAGE),
        ("preferred_roles", {"title": "Phlebotomist"}),
        ("preferred_locations", {"state": "Telangana", "district": "Hyderabad"}),
    ],
)
async def test_every_collection_round_trips(
    client: AsyncClient, headers: dict, collection: str, payload: dict
) -> None:
    body = (await client.post(f"/me/profile/{collection}", headers=headers, json=payload)).json()
    assert len(body[collection]) == 1

    entry_id = body[collection][0]["id"]
    after = (await client.delete(f"/me/profile/{collection}/{entry_id}", headers=headers)).json()
    assert after[collection] == []


async def test_entry_can_be_updated(client: AsyncClient, headers: dict) -> None:
    body = (await client.post("/me/profile/experiences", headers=headers, json=EXPERIENCE)).json()
    entry_id = body["experiences"][0]["id"]
    updated = (
        await client.put(
            f"/me/profile/experiences/{entry_id}",
            headers=headers,
            json={**EXPERIENCE, "role_title": "Senior Ward Attendant"},
        )
    ).json()
    assert updated["experiences"][0]["role_title"] == "Senior Ward Attendant"


async def test_unknown_collection_is_404(client: AsyncClient, headers: dict) -> None:
    res = await client.post("/me/profile/nonsense", headers=headers, json={})
    assert res.status_code == 404


async def test_duplicate_language_is_409(client: AsyncClient, headers: dict) -> None:
    await client.post("/me/profile/languages", headers=headers, json=LANGUAGE)
    dup = await client.post("/me/profile/languages", headers=headers, json=LANGUAGE)
    assert dup.status_code == 409


async def test_invalid_entry_is_422_not_500(client: AsyncClient, headers: dict) -> None:
    """These routes take an untyped body, so FastAPI's automatic 422 does not
    apply and the validation error must be translated explicitly."""
    res = await client.post(
        "/me/profile/experiences",
        headers=headers,
        json={
            "employer_name": "X",
            "role_title": "Y",
            "started_on": "2024-01-01",
            "ended_on": "2023-01-01",
        },
    )
    assert res.status_code == 422


async def test_current_role_cannot_keep_an_end_date(client: AsyncClient, headers: dict) -> None:
    """Otherwise duration calculations would later be wrong."""
    body = (
        await client.post(
            "/me/profile/experiences",
            headers=headers,
            json={**EXPERIENCE, "is_current": True, "ended_on": "2024-01-01"},
        )
    ).json()
    assert body["experiences"][0]["ended_on"] is None


# ------------------------------------------------------------ certifications


async def test_certification_links_to_a_taxonomy_skill(
    client: AsyncClient, headers: dict, db: AsyncSession
) -> None:
    """The link is what will later let a certificate set source='certified'."""
    db.add(Skill(slug="blood-sample-collection", name_en="Blood sample collection"))
    await db.flush()
    body = (
        await client.post(
            "/me/profile/certifications",
            headers=headers,
            json={"name": "Phlebotomy", "skill_slug": "blood-sample-collection"},
        )
    ).json()
    assert body["certifications"][0]["skill"]["slug"] == "blood-sample-collection"


async def test_certification_with_unknown_skill_is_404(client: AsyncClient, headers: dict) -> None:
    res = await client.post(
        "/me/profile/certifications",
        headers=headers,
        json={"name": "X", "skill_slug": "does-not-exist"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------- isolation


async def test_one_candidate_cannot_touch_anothers_entry(
    client: AsyncClient, headers: dict
) -> None:
    """The obvious catastrophic bug: editing someone else's profile by id."""
    mine = (
        await client.post("/me/profile/preferred_roles", headers=headers, json={"title": "Nurse"})
    ).json()
    entry_id = mine["preferred_roles"][0]["id"]

    other = await _auth(client)
    assert (
        await client.delete(f"/me/profile/preferred_roles/{entry_id}", headers=other)
    ).status_code == 404
    assert (
        await client.put(
            f"/me/profile/preferred_roles/{entry_id}", headers=other, json={"title": "Hacked"}
        )
    ).status_code == 404


async def test_sections_require_authentication(client: AsyncClient) -> None:
    assert (await client.post("/me/profile/experiences", json=EXPERIENCE)).status_code == 401


# ------------------------------------------------------- route shadowing


async def test_skills_routes_are_not_captured_by_the_generic_handler(
    client: AsyncClient, headers: dict, db: AsyncSession
) -> None:
    """/me/profile/skills must resolve as skills, not as a collection named
    'skills' -- the same trap as /skills/search versus /skills/{slug}."""
    db.add(Skill(slug="hand-hygiene", name_en="Hand hygiene"))
    await db.flush()
    added = await client.post(
        "/me/profile/skills", headers=headers, json={"skill_slug": "hand-hygiene", "proficiency": 3}
    )
    assert added.status_code == 200
    assert added.json()["skills"][0]["source"] == "self_declared"
    removed = await client.delete("/me/profile/skills/hand-hygiene", headers=headers)
    assert removed.status_code == 200 and removed.json()["skills"] == []


# ------------------------------------------------------------ completeness


async def test_completeness_rises_as_the_profile_fills(
    client: AsyncClient, headers: dict, db: AsyncSession
) -> None:
    db.add(Skill(slug="first-aid", name_en="First aid"))
    await db.flush()

    start = (await client.get("/me/profile", headers=headers)).json()["completeness"]["percent"]
    await client.put(
        "/me/profile",
        headers=headers,
        json={"full_name": "Priya", "headline": "Phlebotomist", "location_state": "Telangana"},
    )
    await client.post(
        "/me/profile/skills", headers=headers, json={"skill_slug": "first-aid", "proficiency": 3}
    )
    await client.post(
        "/me/profile/preferred_roles", headers=headers, json={"title": "Phlebotomist"}
    )
    await client.post("/me/profile/experiences", headers=headers, json=EXPERIENCE)
    await client.post("/me/profile/educations", headers=headers, json=EDUCATION)
    await client.post("/me/profile/languages", headers=headers, json=LANGUAGE)

    body = (await client.get("/me/profile", headers=headers)).json()
    assert start == 0
    assert body["completeness"]["percent"] == 100
    assert body["completeness"]["missing"] == []


async def test_onboarding_flag_starts_unset_and_can_be_completed(
    client: AsyncClient, headers: dict
) -> None:
    """Drives wizard-on-first-visit, sectioned editor thereafter."""
    assert (await client.get("/me/profile", headers=headers)).json()[
        "onboarding_completed_at"
    ] is None
    done = await client.post("/me/profile/onboarding/complete", headers=headers)
    assert done.status_code == 200 and done.json()["onboarding_completed_at"] is not None
