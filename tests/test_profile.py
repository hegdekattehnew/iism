"""Sprint 4: the candidate profile — the third side of the graph."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills import Skill


async def _auth(client: AsyncClient) -> dict[str, str]:
    phone = "9" + uuid.uuid4().int.__str__()[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (await client.post("/auth/otp/verify", json={"phone": phone, "code": code})).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _skill(db: AsyncSession, slug: str) -> Skill:
    skill = Skill(slug=slug, name_en=slug.replace("-", " ").title(), skill_type="technical")
    db.add(skill)
    await db.flush()
    return skill


async def test_profile_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/me/profile")).status_code == 401


async def test_profile_is_created_lazily_on_first_read(client: AsyncClient) -> None:
    """Sign-in should not have to decide whether someone is a candidate."""
    res = await client.get("/me/profile", headers=await _auth(client))
    assert res.status_code == 200
    assert res.json()["skills"] == []
    assert res.json()["years_experience"] == 0


async def test_profile_update_round_trips(client: AsyncClient) -> None:
    headers = await _auth(client)
    await client.put(
        "/me/profile",
        headers=headers,
        json={
            "headline": "Aspiring phlebotomist",
            "location_state": "Telangana",
            "location_district": "Hyderabad",
            "years_experience": 2,
            "education_level": "higher_secondary",
        },
    )
    body = (await client.get("/me/profile", headers=headers)).json()
    assert body["headline"] == "Aspiring phlebotomist"
    assert body["education_level"] == "higher_secondary"
    assert body["years_experience"] == 2


async def test_update_rejects_an_invalid_education_level(client: AsyncClient) -> None:
    res = await client.put(
        "/me/profile",
        headers=await _auth(client),
        json={"years_experience": 0, "education_level": "phd"},
    )
    assert res.status_code == 422


async def test_update_rejects_impossible_experience(client: AsyncClient) -> None:
    res = await client.put(
        "/me/profile", headers=await _auth(client), json={"years_experience": 99}
    )
    assert res.status_code == 422


async def test_added_skills_are_marked_self_declared(client: AsyncClient, db: AsyncSession) -> None:
    """Anything a user types about themselves is self-declared. Only an
    assessment or certificate may set a stronger source (ADR-007)."""
    await _skill(db, "hand-hygiene")
    headers = await _auth(client)
    body = (
        await client.post(
            "/me/profile/skills",
            headers=headers,
            json={"skill_slug": "hand-hygiene", "proficiency": 4},
        )
    ).json()
    assert [(s["skill"]["slug"], s["proficiency"], s["source"]) for s in body["skills"]] == [
        ("hand-hygiene", 4, "self_declared")
    ]


async def test_re_adding_a_skill_updates_proficiency_rather_than_erroring(
    client: AsyncClient, db: AsyncSession
) -> None:
    await _skill(db, "teamwork")
    headers = await _auth(client)
    for level in (2, 5):
        body = (
            await client.post(
                "/me/profile/skills",
                headers=headers,
                json={"skill_slug": "teamwork", "proficiency": level},
            )
        ).json()
    assert len(body["skills"]) == 1
    assert body["skills"][0]["proficiency"] == 5


async def test_unknown_skill_is_rejected(client: AsyncClient) -> None:
    res = await client.post(
        "/me/profile/skills",
        headers=await _auth(client),
        json={"skill_slug": "does-not-exist", "proficiency": 3},
    )
    assert res.status_code == 404


async def test_proficiency_is_bounded(client: AsyncClient, db: AsyncSession) -> None:
    await _skill(db, "first-aid")
    res = await client.post(
        "/me/profile/skills",
        headers=await _auth(client),
        json={"skill_slug": "first-aid", "proficiency": 9},
    )
    assert res.status_code == 422


async def test_skill_can_be_removed(client: AsyncClient, db: AsyncSession) -> None:
    await _skill(db, "bed-making")
    headers = await _auth(client)
    await client.post(
        "/me/profile/skills",
        headers=headers,
        json={"skill_slug": "bed-making", "proficiency": 3},
    )
    body = (await client.delete("/me/profile/skills/bed-making", headers=headers)).json()
    assert body["skills"] == []


async def test_profiles_are_isolated_between_users(client: AsyncClient, db: AsyncSession) -> None:
    """The obvious catastrophic bug: one candidate seeing another's profile."""
    await _skill(db, "cpr")
    a, b = await _auth(client), await _auth(client)
    await client.post("/me/profile/skills", headers=a, json={"skill_slug": "cpr", "proficiency": 5})
    assert (await client.get("/me/profile", headers=b)).json()["skills"] == []


async def test_profile_survives_a_new_session(client: AsyncClient, db: AsyncSession) -> None:
    """Sign out and back in; the profile must still be there."""
    await _skill(db, "workplace-safety")
    phone = "9" + uuid.uuid4().int.__str__()[:9]

    async def sign_in() -> dict[str, str]:
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        body = (await client.post("/auth/otp/verify", json={"phone": phone, "code": code})).json()
        return {"authorization": f"Bearer {body['access_token']}"}

    first = await sign_in()
    await client.post(
        "/me/profile/skills",
        headers=first,
        json={"skill_slug": "workplace-safety", "proficiency": 4},
    )
    second = await sign_in()
    body = (await client.get("/me/profile", headers=second)).json()
    assert [s["skill"]["slug"] for s in body["skills"]] == ["workplace-safety"]
