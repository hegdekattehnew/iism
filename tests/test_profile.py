"""Sprint 4: the candidate profile — the third side of the graph."""

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics import AnalyticsEvent
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateSkill
from api.modules.marketplace.profile_service import MAX_SKILLS_PER_PROFILE
from api.modules.skills import Skill


async def _auth(client: AsyncClient) -> dict[str, str]:
    phone = "9" + uuid.uuid4().int.__str__()[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _skill(db: AsyncSession, slug: str) -> Skill:
    skill = Skill(slug=slug, name=slug.replace("-", " ").title(), skill_type="technical")
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
        body = (
            await client.post(
                "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
            )
        ).json()
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


# ------------------------------------------------------ Sprint 23: bulk add


async def _skills(db: AsyncSession, n: int) -> list[str]:
    tag = uuid.uuid4().hex[:6]
    return [(await _skill(db, f"bulk-{tag}-{i}")).slug for i in range(n)]


async def _held(db: AsyncSession) -> int:
    return (await db.scalar(select(func.count()).select_from(CandidateSkill))) or 0


def _items(slugs: list[str], proficiency: int = 3) -> list[dict]:
    return [{"skill_slug": s, "proficiency": proficiency} for s in slugs]


class TestAddingSeveralAtOnce:
    """Ticking the standards of a suggested role is one decision, so it is one
    request. Everything here is about what that request may and may not do."""

    async def test_every_row_is_self_declared(self, client: AsyncClient, db: AsyncSession) -> None:
        """A ticked suggestion is still the candidate's own claim. `inferred`
        would score 0.7 against 0.6 and reward whoever took the easy path."""
        headers = await _auth(client)
        slugs = await _skills(db, 4)
        body = (
            await client.post(
                "/me/profile/skills/bulk", headers=headers, json={"items": _items(slugs)}
            )
        ).json()
        assert len(body["skills"]) == 4
        assert {s["source"] for s in body["skills"]} == {"self_declared"}

    async def test_re_adding_updates_rather_than_duplicating(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _auth(client)
        slugs = await _skills(db, 3)
        await client.post("/me/profile/skills/bulk", headers=headers, json={"items": _items(slugs)})
        body = (
            await client.post(
                "/me/profile/skills/bulk", headers=headers, json={"items": _items(slugs, 5)}
            )
        ).json()
        assert len(body["skills"]) == 3
        assert {s["proficiency"] for s in body["skills"]} == {5}

    async def test_a_batch_that_would_cross_the_cap_is_refused_whole(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Eight ticked, three land, and nothing says which five went: worse than
        a refusal. So it is a refusal, and nothing is written."""
        headers = await _auth(client)
        first = await _skills(db, MAX_SKILLS_PER_PROFILE - 2)
        await client.post("/me/profile/skills/bulk", headers=headers, json={"items": _items(first)})
        before = await _held(db)

        response = await client.post(
            "/me/profile/skills/bulk", headers=headers, json={"items": _items(await _skills(db, 3))}
        )
        assert response.status_code == 400
        assert "room for 2 more" in response.json()["detail"]
        assert await _held(db) == before

    async def test_re_adding_held_skills_does_not_count_toward_the_cap(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _auth(client)
        full = await _skills(db, MAX_SKILLS_PER_PROFILE)
        await client.post("/me/profile/skills/bulk", headers=headers, json={"items": _items(full)})
        response = await client.post(
            "/me/profile/skills/bulk", headers=headers, json={"items": _items(full[:10], 4)}
        )
        assert response.status_code == 200

    async def test_one_unknown_standard_writes_nothing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _auth(client)
        slugs = await _skills(db, 2)
        before = await _held(db)
        response = await client.post(
            "/me/profile/skills/bulk",
            headers=headers,
            json={"items": _items([slugs[0], "no-such-standard", slugs[1]])},
        )
        assert response.status_code == 404
        assert "no-such-standard" in response.json()["detail"]
        assert await _held(db) == before

    async def test_an_empty_batch_is_refused(self, client: AsyncClient) -> None:
        response = await client.post(
            "/me/profile/skills/bulk", headers=await _auth(client), json={"items": []}
        )
        assert response.status_code == 422

    async def test_the_role_they_came_from_becomes_a_preferred_role_once(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The candidate has just named their target -- the fact the completeness
        meter weights highest. Recorded once, however often they come back."""
        headers = await _auth(client)
        slugs = await _skills(db, 2)
        payload = {"items": _items(slugs), "preferred_role_title": "General Duty Assistant"}
        await client.post("/me/profile/skills/bulk", headers=headers, json=payload)
        payload["preferred_role_title"] = "general duty assistant"
        response = await client.post("/me/profile/skills/bulk", headers=headers, json=payload)
        assert response.status_code == 200
        roles = response.json()["preferred_roles"]
        assert [r["title"] for r in roles] == ["General Duty Assistant"]
        assert "preferred_roles" not in response.json()["completeness"]["missing"]

    async def test_it_is_not_read_as_a_profile_collection(self, client: AsyncClient) -> None:
        """`/me/profile/{collection}` would otherwise capture `skills` and answer
        "Unknown profile section" to a perfectly good request."""
        response = await client.post(
            "/me/profile/skills/bulk", headers=await _auth(client), json={"items": []}
        )
        assert response.status_code == 422  # validated as a bulk add, not a 404 section

    async def test_it_is_measured_in_counts_only(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _auth(client)
        slugs = await _skills(db, 3)
        await client.post(
            "/me/profile/skills/bulk",
            headers=headers,
            json={"items": _items(slugs), "preferred_role_title": "Phlebotomist"},
        )
        event = await db.scalar(
            select(AnalyticsEvent)
            .where(AnalyticsEvent.name == "skills_bulk_added")
            .order_by(AnalyticsEvent.occurred_at.desc())
        )
        assert event.payload == {"added": 3, "updated": 0, "from_role": True}


# --------------------------- Sprint 35, BL-3.1/BL-3.2: evidence outranks a claim


class TestVerifiedEvidenceNeverDowngrades:
    """`record_verified_skill` (Sprint 35) is the second caller `_write_skills`
    ever had. This is the property its whole design depends on: an evidenced
    source can raise what a self-declared row says, and a later self-declared
    re-add can never lower it back down."""

    async def test_an_assessed_result_upgrades_a_self_declared_skill(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        from api.modules.marketplace import get_or_create_profile, record_verified_skill

        skill = await _skill(db, "wound-care")
        headers = await _auth(client)
        me = (await client.get("/auth/me", headers=headers)).json()
        await client.post(
            "/me/profile/skills",
            headers=headers,
            json={"skill_slug": "wound-care", "proficiency": 2},
        )

        profile = await get_or_create_profile(db, uuid.UUID(me["id"]))
        await record_verified_skill(db, profile, "wound-care", source="assessed")

        row = await db.scalar(
            select(CandidateSkill).where(
                CandidateSkill.profile_id == profile.id, CandidateSkill.skill_id == skill.id
            )
        )
        assert row is not None
        assert row.source == "assessed"

    async def test_re_adding_self_declared_never_downgrades_a_verified_skill(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        from api.modules.marketplace import get_or_create_profile, record_verified_skill

        skill = await _skill(db, "sterilisation")
        headers = await _auth(client)
        me = (await client.get("/auth/me", headers=headers)).json()

        profile = await get_or_create_profile(db, uuid.UUID(me["id"]))
        await record_verified_skill(db, profile, "sterilisation", source="certified")

        # The candidate edits their own proficiency afterwards -- a
        # self-declared write on the same standard.
        await client.post(
            "/me/profile/skills",
            headers=headers,
            json={"skill_slug": "sterilisation", "proficiency": 5},
        )

        row = await db.scalar(
            select(CandidateSkill).where(
                CandidateSkill.profile_id == profile.id, CandidateSkill.skill_id == skill.id
            )
        )
        assert row is not None
        assert row.source == "certified"
        assert row.proficiency == 5  # the proficiency itself still updates

    async def test_record_verified_skill_refuses_a_self_declared_source(
        self, db: AsyncSession
    ) -> None:
        import pytest

        from api.modules.marketplace import get_or_create_profile, record_verified_skill

        headers_user_id = uuid.uuid4()
        db.add(User(id=headers_user_id, phone=f"+9199{uuid.uuid4().int % 100000000:08d}"))
        await db.flush()
        profile = await get_or_create_profile(db, headers_user_id)
        with pytest.raises(ValueError, match="evidenced sources only"):
            await record_verified_skill(db, profile, "anything", source="self_declared")


def test_skill_sources_are_ordered_by_evidentiary_strength() -> None:
    """`_write_skills`'s upgrade check compares `SKILL_SOURCES.index(...)`
    directly, so this tuple's order **is** the evidence ladder -- it must
    stay in step with `EVIDENCE_WEIGHT`'s own ascending order, or an upgrade
    could silently downgrade a candidate's actual score."""
    from api.modules.marketplace.models import SKILL_SOURCES
    from api.modules.matching.scoring import EVIDENCE_WEIGHT

    by_weight = tuple(sorted(EVIDENCE_WEIGHT, key=lambda source: EVIDENCE_WEIGHT[source]))
    assert by_weight == SKILL_SOURCES
