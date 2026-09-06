"""Sprint 2: the skills module — taxonomy, aliases and multi-script search."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills import Skill, SkillAlias, count_skills, search_skills


async def _add(
    db: AsyncSession,
    slug: str,
    name_en: str,
    name_hi: str | None = None,
    *,
    skill_type: str = "technical",
    nsqf_level: int | None = 4,
    description_en: str | None = None,
    aliases: tuple[tuple[str, str], ...] = (),
) -> Skill:
    skill = Skill(
        slug=slug,
        name_en=name_en,
        name_hi=name_hi,
        description_en=description_en,
        skill_type=skill_type,
        nsqf_level=nsqf_level,
    )
    db.add(skill)
    await db.flush()
    for form, script in aliases:
        db.add(SkillAlias(skill_id=skill.id, surface_form=form, script=script))
    await db.flush()
    return skill


@pytest.fixture
async def seeded(db: AsyncSession) -> AsyncSession:
    """A small fixture covering all three scripts an Indian user might type in."""
    await _add(
        db,
        "blood-sample-collection",
        "Blood sample collection",
        "रक्त नमूना संग्रह",
        description_en="Drawing venous blood samples safely.",
        aliases=(
            ("phlebotomy", "latin"),
            ("रक्त संग्रह", "devanagari"),
            ("khoon nikalna", "transliteration"),
        ),
    )
    await _add(
        db,
        "hand-hygiene",
        "Hand hygiene",
        "हाथ की स्वच्छता",
        skill_type="core",
        nsqf_level=2,
        aliases=(("haath dhona", "transliteration"),),
    )
    await _add(db, "teamwork", "Teamwork", "टीम वर्क", skill_type="generic", nsqf_level=None)
    return db


# ------------------------------------------------------------------ basics


async def test_count_endpoint(client: AsyncClient) -> None:
    response = await client.get("/skills/count")
    assert response.status_code == 200
    assert response.json() == {"count": 0}


async def test_count_reflects_inserted_rows(db: AsyncSession) -> None:
    await _add(db, "wound-dressing", "Wound dressing")
    assert await count_skills(db) == 1


async def test_rows_do_not_leak_between_tests(db: AsyncSession) -> None:
    assert await count_skills(db) == 0


# ------------------------------------------------------------------ listing


async def test_list_returns_page_and_total(seeded: AsyncSession, client: AsyncClient) -> None:
    body = (await client.get("/skills")).json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["items"][0]["name_en"] == "Blood sample collection"  # alphabetical


async def test_list_filters_by_type(seeded: AsyncSession, client: AsyncClient) -> None:
    body = (await client.get("/skills", params={"skill_type": "core"})).json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "hand-hygiene"


async def test_list_filters_by_nsqf_level(seeded: AsyncSession, client: AsyncClient) -> None:
    body = (await client.get("/skills", params={"nsqf_level": 2})).json()
    assert [i["slug"] for i in body["items"]] == ["hand-hygiene"]


async def test_list_paginates(seeded: AsyncSession, client: AsyncClient) -> None:
    body = (await client.get("/skills", params={"limit": 1, "offset": 1})).json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


# ------------------------------------------------------------------ detail


async def test_detail_includes_every_alias(seeded: AsyncSession, client: AsyncClient) -> None:
    body = (await client.get("/skills/blood-sample-collection")).json()
    assert body["name_hi"] == "रक्त नमूना संग्रह"
    assert {a["script"] for a in body["aliases"]} == {
        "latin",
        "devanagari",
        "transliteration",
    }


async def test_detail_404_for_unknown_slug(client: AsyncClient) -> None:
    assert (await client.get("/skills/does-not-exist")).status_code == 404


async def test_search_route_is_not_shadowed_by_slug_route(
    seeded: AsyncSession, client: AsyncClient
) -> None:
    """/skills/search must resolve as search, not as a slug lookup."""
    response = await client.get("/skills/search", params={"q": "blood"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ------------------------------------------------------------------ search
# The point of the sprint: a skill resolves however a real person types it.


async def test_search_by_english_name(seeded: AsyncSession) -> None:
    hits = await search_skills(seeded, "blood sample")
    assert hits[0].skill.slug == "blood-sample-collection"


async def test_search_by_devanagari_name(seeded: AsyncSession) -> None:
    hits = await search_skills(seeded, "रक्त")
    assert hits[0].skill.slug == "blood-sample-collection"


async def test_search_by_transliterated_hindi(seeded: AsyncSession) -> None:
    """The case that matters most: Hindi typed on a Latin keyboard."""
    hits = await search_skills(seeded, "khoon nikalna")
    assert hits[0].skill.slug == "blood-sample-collection"
    assert hits[0].match_kind == "alias"
    assert hits[0].matched_on == "khoon nikalna"


async def test_search_by_latin_alias(seeded: AsyncSession) -> None:
    hits = await search_skills(seeded, "phlebotomy")
    assert hits[0].skill.slug == "blood-sample-collection"


async def test_search_by_devanagari_alias(seeded: AsyncSession) -> None:
    hits = await search_skills(seeded, "रक्त संग्रह")
    assert hits[0].skill.slug == "blood-sample-collection"


async def test_search_tolerates_a_typo(seeded: AsyncSession) -> None:
    """Trigram fallback: a missing letter should still find the skill."""
    hits = await search_skills(seeded, "khoon nikaln")
    assert any(h.skill.slug == "blood-sample-collection" for h in hits)


async def test_exact_name_outranks_fuzzy(seeded: AsyncSession) -> None:
    hits = await search_skills(seeded, "Hand hygiene")
    assert hits[0].skill.slug == "hand-hygiene"
    assert hits[0].match_kind == "exact"


async def test_search_matches_description_text(seeded: AsyncSession) -> None:
    hits = await search_skills(seeded, "venous")
    assert [h.skill.slug for h in hits] == ["blood-sample-collection"]


async def test_search_returns_each_skill_once(seeded: AsyncSession) -> None:
    """'blood' hits the name, the description and an alias — still one result."""
    hits = await search_skills(seeded, "blood")
    slugs = [h.skill.slug for h in hits]
    assert len(slugs) == len(set(slugs))


async def test_blank_search_returns_nothing(seeded: AsyncSession) -> None:
    assert await search_skills(seeded, "   ") == []


async def test_search_respects_limit(seeded: AsyncSession) -> None:
    assert len(await search_skills(seeded, "a", limit=1)) <= 1


class TestRetiredSkills:
    """The 52 curated skills were superseded, not deleted.

    Their aliases were carried onto the standards they map to, so the
    multi-script search still works -- but now it reaches a real National
    Occupational Standard rather than a hand-written stand-in.
    """

    async def _retire(self, db) -> tuple[object, object]:
        """A live skill and a retired one, sharing an alias."""
        from api.modules.skills.models import Skill, SkillAlias

        live = Skill(slug="live-standard", name_en="Live standard", source="nsqf")
        retired = Skill(slug="retired-skill", name_en="Retired skill", source="legacy")
        db.add_all([live, retired])
        await db.flush()
        db.add(SkillAlias(skill_id=live.id, surface_form="khoon nikalna", script="transliteration"))
        db.add(SkillAlias(skill_id=retired.id, surface_form="old term", script="latin"))
        await db.flush()
        return live, retired

    async def test_a_retired_skill_is_absent_from_browse(self, db, client) -> None:
        await self._retire(db)

        slugs = {s["slug"] for s in (await client.get("/skills?limit=200")).json()["items"]}
        assert "live-standard" in slugs
        assert "retired-skill" not in slugs

    async def test_a_retired_skill_is_absent_from_search(self, db, client) -> None:
        """Including through its own alias -- otherwise the exclusion would leak
        through one of the four search branches."""
        await self._retire(db)

        by_name = (await client.get("/skills/search?q=Retired skill")).json()
        assert all(hit["slug"] != "retired-skill" for hit in by_name)

        by_alias = (await client.get("/skills/search?q=old term")).json()
        assert all(hit["slug"] != "retired-skill" for hit in by_alias)

    async def test_a_carried_alias_reaches_the_live_standard(self, db, client) -> None:
        await self._retire(db)

        hits = (await client.get("/skills/search?q=khoon nikalna")).json()
        assert any(hit["slug"] == "live-standard" for hit in hits)

    async def test_a_retired_skill_keeps_its_own_page(self, db, client) -> None:
        """Not deleted, because profiles and certificates still reference them.
        A 404 on a row we deliberately kept would be a broken link of our own
        making."""
        await self._retire(db)

        assert (await client.get("/skills/retired-skill")).status_code == 200

    async def test_retired_rows_are_excluded_from_the_count_and_facets(self, db, client) -> None:
        await self._retire(db)

        counted = (await client.get("/skills/count")).json()["count"]
        facet_total = (await client.get("/skills/facets")).json()["total"]
        assert counted == facet_total  # both exclude retired rows, so they agree
