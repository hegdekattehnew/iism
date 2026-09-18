"""Sprint 23: name your job, and be offered the standards behind it.

A candidate cannot name a National Occupational Standard, but they can name
their job -- and every qualification pack in the corpus carries a `job_role`.
These tests use a hand-built slice of the corpus that reproduces each thing the
real one does to a naive search: a `-SI` variant beside its base code, the same
qualification reissued under a longer prefixed code, a pack with no standards,
a role that exists only as a variant, and a retired version.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import AnalyticsEvent
from api.modules.skills import Skill
from api.modules.skills.hierarchy import QpSkill, QualificationPack, Sector
from api.modules.skills.role_aliases import MIN_ALIAS_PREFIX, ROLE_ALIASES, alias_scores

TIER = {"exact": 4, "alias": 4, "prefix": 3, "contains": 2, "fuzzy": 1}


def _standard(code: str, name: str) -> Skill:
    return Skill(
        slug=f"std-{code.lower().replace('/', '-')}-{uuid.uuid4().hex[:6]}",
        name=name,
        nos_code=f"{code}-{uuid.uuid4().hex[:6]}",
        source="nsqf",
        nsqf_level=Decimal("3"),
    )


@pytest.fixture
async def corpus(db: AsyncSession) -> dict[str, QualificationPack]:
    sector = Sector(
        sector_ref=f"s-{uuid.uuid4().hex[:6]}", name="Healthcare", slug=f"hc-{uuid.uuid4().hex[:6]}"
    )
    db.add(sector)
    await db.flush()

    standards = [_standard(f"HSS/N{i:04d}", f"Standard {i}") for i in range(10)]
    db.add_all(standards)
    await db.flush()

    packs: dict[str, QualificationPack] = {}

    def pack(
        key: str,
        code: str,
        role: str,
        links: list[tuple[int, str, str | None, str | None]],
        *,
        current: bool = True,
    ) -> None:
        qp = QualificationPack(
            qp_code=code,
            version="1.0",
            slug=f"{key}-{uuid.uuid4().hex[:6]}",
            name=f"{role} qualification",
            job_role=role,
            nsqf_level=Decimal("4"),
            is_current=current,
            sector_id=sector.id,
        )
        db.add(qp)
        packs[key] = qp
        pending.append((qp, links))

    pending: list[tuple[QualificationPack, list[tuple[int, str, str | None, str | None]]]] = []
    c = "compulsory"
    # The base code, a -SI variant, and a reissue under a longer prefixed code
    # that happens to carry *more* standards. The base must still win.
    pack(
        "phleb",
        "HSS/Q9001",
        "Phlebotomist",
        [(0, c, None, "30"), (1, c, None, "20"), (2, c, None, None)],
    )
    pack("phleb_si", "HSS/Q9001-SI001", "Phlebotomist", [(0, c, None, None)])
    pack(
        "phleb_dgt",
        "DGT/HSS/Q9001",
        "Phlebotomist",
        [(0, c, None, None), (1, c, None, None), (2, c, None, None), (3, c, None, None)],
    )
    # Electives in a group, so the grouping has something to preserve.
    pack(
        "gda",
        "CII/HSS/Q5101",
        "General Duty Assistant",
        [
            (4, c, None, "10"),
            (5, "elective", "Elective 1: Critical Care", None),
            (6, "elective", "Elective 1: Critical Care", None),
            (7, "optional", None, None),
        ],
    )
    pack("beautician", "BWS/Q0113", "Beautician", [(8, c, None, None)])
    pack("asst_beautician", "BWS/Q0701", "Assistant Beautician", [(8, c, None, None)])
    pack("food_delivery", "THC/Q2902", "Food Delivery Associate", [(9, c, None, None)])
    pack("ecommerce", "LSC/Q2603", "E-commerce Delivery Associate", [(9, c, None, None)])
    pack("empty", "XYZ/Q0001", "Empty Role", [])
    pack("variant_only", "ABC/Q0002-SI001", "Variant Only Role", [(3, c, None, None)])
    pack("retired", "OLD/Q0003", "Retired Role", [(3, c, None, None)], current=False)

    await db.flush()
    for qp, links in pending:
        for idx, requirement, group, weightage in links:
            db.add(
                QpSkill(
                    qp_id=qp.id,
                    skill_id=standards[idx].id,
                    requirement=requirement,
                    group_name=group,
                    weightage=Decimal(weightage) if weightage else None,
                )
            )
    await db.commit()
    return packs


async def _search(client: AsyncClient, q: str) -> list[dict]:
    response = await client.get("/roles/search", params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()


class TestSearchingForARole:
    async def test_an_exact_title_outranks_one_that_merely_contains_it(
        self, client, corpus
    ) -> None:
        hits = await _search(client, "beautician")
        assert [h["job_role"] for h in hits] == ["Beautician", "Assistant Beautician"]
        assert [h["match_kind"] for h in hits] == ["exact", "contains"]

    async def test_a_half_typed_word_is_a_prefix_match(self, client, corpus) -> None:
        hits = await _search(client, "beaut")
        assert hits[0]["job_role"] == "Beautician"
        assert hits[0]["match_kind"] == "prefix"

    async def test_a_misremembered_title_is_found_fuzzily(self, client, corpus) -> None:
        """The whole reason for the trigram branch: nobody types the corpus's
        own title, and substring matching alone finds nothing here."""
        hits = await _search(client, "delivery guy")
        assert {h["job_role"] for h in hits} >= {"Food Delivery Associate"}
        assert all(h["match_kind"] == "fuzzy" for h in hits)

    @pytest.mark.parametrize("q", ["beautician", "beaut", "delivery", "ward boy", "phleb"])
    async def test_a_guess_never_outranks_something_typed(self, client, corpus, q: str) -> None:
        tiers = [TIER[h["match_kind"]] for h in await _search(client, q)]
        assert tiers == sorted(tiers, reverse=True)

    async def test_nothing_matching_is_an_empty_list_not_an_error(self, client, corpus) -> None:
        assert await _search(client, "xyzzyq") == []

    async def test_an_empty_query_is_refused(self, client, corpus) -> None:
        assert (await client.get("/roles/search", params={"q": ""})).status_code == 422


class TestTheAliasMap:
    """ "Ward boy" shares no letters with "General Duty Assistant", so no fuzzy
    search can find it -- and it is what the person this product is for says."""

    async def test_ward_boy_reaches_general_duty_assistant(self, client, corpus) -> None:
        hits = await _search(client, "ward boy")
        assert hits[0]["job_role"] == "General Duty Assistant"
        assert hits[0]["match_kind"] == "alias"
        assert hits[0]["matched_on"] == "ward boy"

    async def test_it_works_in_devanagari(self, client, corpus) -> None:
        hits = await _search(client, "वार्ड बॉय")
        assert hits[0]["job_role"] == "General Duty Assistant"

    async def test_a_half_typed_alias_still_finds_its_role(self, client, corpus) -> None:
        hits = await _search(client, "ward b")
        assert hits[0]["job_role"] == "General Duty Assistant"

    async def test_the_role_named_literally_is_not_reported_as_an_alias(
        self, client, corpus
    ) -> None:
        """ "delivery boy" reaches E-commerce Delivery Associate by alias; typing
        the title itself must say it matched the title."""
        hits = await _search(client, "e-commerce delivery associate")
        assert hits[0]["match_kind"] == "exact"

    def test_every_key_is_written_the_way_it_is_looked_up(self) -> None:
        # A key with a capital or a double space can never match: the query is
        # lower-cased and whitespace-collapsed before comparison.
        for key, value in ROLE_ALIASES.items():
            assert key == " ".join(key.lower().split()), key
            assert value.strip(), key

    def test_two_letters_are_not_enough_to_claim_a_role(self) -> None:
        assert alias_scores("wa") == {}
        assert alias_scores("war")  # MIN_ALIAS_PREFIX characters is enough
        assert MIN_ALIAS_PREFIX == 3


class TestOneRowPerRole:
    async def test_the_base_code_represents_its_variants_and_reissues(self, client, corpus) -> None:
        """The -SI variant has fewer standards and the reissue has more; neither
        is the qualification. The SSC's own base code is."""
        hits = await _search(client, "phlebotomist")
        assert len(hits) == 1
        assert hits[0]["qp_code"] == "HSS/Q9001"
        assert hits[0]["variants"] == 3
        assert hits[0]["standards_count"] == 3

    async def test_a_role_that_exists_only_as_a_variant_is_still_reachable(
        self, client, corpus
    ) -> None:
        hits = await _search(client, "variant only")
        assert [h["qp_code"] for h in hits] == ["ABC/Q0002-SI001"]

    async def test_a_pack_with_no_standards_is_never_offered(self, client, corpus) -> None:
        """Choosing it would offer nothing to tick."""
        assert await _search(client, "empty role") == []

    async def test_a_retired_version_is_never_offered(self, client, corpus) -> None:
        assert await _search(client, "retired role") == []


class TestAQualificationsStandards:
    async def test_electives_keep_their_group_and_come_after_the_compulsory(
        self, client, corpus
    ) -> None:
        """Flattening would turn "choose one of these" into "all of these are
        required", which is not what the qualification says."""
        body = (await client.get(f"/roles/{corpus['gda'].slug}/standards")).json()
        assert body["qp_code"] == "CII/HSS/Q5101"
        assert [s["requirement"] for s in body["standards"]] == [
            "compulsory",
            "elective",
            "elective",
            "optional",
        ]
        assert {s["group_name"] for s in body["standards"] if s["requirement"] == "elective"} == {
            "Elective 1: Critical Care"
        }
        # Each is a real standard the profile can hold, code included.
        assert all(s["slug"] and s["nos_code"] for s in body["standards"])

    async def test_heavier_compulsory_standards_come_first(self, client, corpus) -> None:
        body = (await client.get(f"/roles/{corpus['phleb'].slug}/standards")).json()
        assert [s["weightage"] for s in body["standards"]] == [30.0, 20.0, None]

    async def test_it_says_how_many_versions_share_the_name(self, client, corpus) -> None:
        body = (await client.get(f"/roles/{corpus['phleb'].slug}/standards")).json()
        assert body["variants"] == 3

    async def test_an_unknown_qualification_is_404(self, client, corpus) -> None:
        assert (await client.get("/roles/no-such-pack/standards")).status_code == 404

    async def test_looking_is_measured_without_identifying_anyone(
        self, client, corpus, db: AsyncSession
    ) -> None:
        await client.get(f"/roles/{corpus['gda'].slug}/standards")
        event = await db.scalar(
            select(AnalyticsEvent).where(
                AnalyticsEvent.name == "role_suggested",
                AnalyticsEvent.subject_id == corpus["gda"].id,
            )
        )
        assert event is not None
        assert event.payload == {"standards": 4, "variants": 1}
