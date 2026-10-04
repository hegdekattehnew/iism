"""Role search you can trust (Sprint 43, ADR-050).

Three faults found by running the search against the real corpus, which the
original fixture corpus was too small to show: a disability-track pack leading a
general one, a half-typed alias losing to a literal prefix, and a multi-word
query finding nothing. Each test is built so that **that rule alone** decides the
result, so deleting the rule fails exactly that test.
"""

import itertools
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills import search_roles
from api.modules.skills.hierarchy import QpSkill, QualificationPack, RoleAlias, Sector
from api.modules.skills.models import Skill
from api.modules.skills.service import _query_terms, alias_prefix_collisions, alias_problems

_n = itertools.count(1)


async def _sector(db: AsyncSession) -> Sector:
    i = next(_n)
    sector = Sector(sector_ref=f"rst-{i}", name="Healthcare", slug=f"rst-{i}")
    db.add(sector)
    await db.flush()
    return sector


async def _pack(db: AsyncSession, sector: Sector, code: str, role: str) -> QualificationPack:
    """A current pack with one standard, so role search is willing to offer it."""
    i = next(_n)
    skill = Skill(
        slug=f"rst-skill-{i}", name=f"Unit {i}", skill_type="technical",
        nsqf_level=Decimal("3"), nos_code=f"RST/N{i:04d}", source="nsqf",
    )  # fmt: skip
    db.add(skill)
    await db.flush()
    pack = QualificationPack(
        qp_code=code, version="1.0", slug=f"rst-pack-{i}", name=f"{role} qualification",
        job_role=role, nsqf_level=Decimal("3"), is_current=True, sector_id=sector.id,
    )  # fmt: skip
    db.add(pack)
    await db.flush()
    db.add(QpSkill(qp_id=pack.id, skill_id=skill.id, requirement="compulsory"))
    await db.flush()
    return pack


async def _roles(db: AsyncSession, query: str) -> list[str]:
    return [h.job_role for h in await search_roles(db, query)]


class TestDisabilityTrackPacks:
    async def test_a_general_role_outranks_a_disability_track_one_of_the_same_quality(
        self, db: AsyncSession
    ) -> None:
        """ "data entry operator" led with three Divyangjan packs. The general role
        is a whole-string *contains* and the disability-track one a *prefix*, so
        without the demotion the prefix wins."""
        sector = await _sector(db)
        await _pack(db, sector, "PWD/SSC/Q2201", "Data Entry Operator (Divyangjan)")
        await _pack(db, sector, "SSC/Q2202", "Domestic Data Entry Operator")
        assert await _roles(db, "data entry operator") == [
            "Domestic Data Entry Operator",
            "Data Entry Operator (Divyangjan)",
        ]

    async def test_it_is_a_demotion_not_a_hiding(self, db: AsyncSession) -> None:
        """Where the disability-track pack is the only literal match it is still
        offered, and still ahead of a weaker guess."""
        sector = await _sector(db)
        await _pack(db, sector, "PWD/MEP/Q0301", "Barista Executive (Divyangjan)")
        await _pack(db, sector, "MEP/Q0302", "Bar Attendant")
        assert (await _roles(db, "barista"))[0] == "Barista Executive (Divyangjan)"

    @pytest.mark.parametrize(
        ("query", "disability_track", "general"),
        [
            ("pwd", "Pwd Helper", "Data Pwd Operator"),
            ("divyang", "Divyangjan Helper", "Data Divyangjan Operator"),
            ("disab", "Disability Helper", "Data Disability Operator"),
        ],
    )
    async def test_asking_for_one_removes_the_demotion(
        self, db: AsyncSession, query: str, disability_track: str, general: str
    ) -> None:
        """The same two packs in the same tiers as the demotion test: a prefix against
        a contains. Only the word in the query differs, and with it the order flips."""
        sector = await _sector(db)
        await _pack(db, sector, "PWD/SSC/Q2301", disability_track)
        await _pack(db, sector, "SSC/Q2302", general)
        assert await _roles(db, query) == [disability_track, general]

    async def test_an_exact_title_in_full_is_never_demoted(self, db: AsyncSession) -> None:
        """ "Pressman" exists only as a disability-track pack, and somebody who typed
        it in full must not be shown something else first."""
        sector = await _sector(db)
        await _pack(db, sector, "PWD/PRN/Q0401", "Pressman")
        await _pack(db, sector, "PRN/Q0402", "Pressman-Stitched Items")
        assert (await _roles(db, "pressman"))[0] == "Pressman"

    async def test_a_general_pack_stands_for_a_role_even_with_more_path_segments(
        self, db: AsyncSession
    ) -> None:
        """The representative rule used to prefer the *fewest* `/` segments, which
        favoured a general pack only by coincidence. Here the disability-track code
        has fewer segments, so the old order would have picked it."""
        sector = await _sector(db)
        await _pack(db, sector, "PWD/Q0501", "Hotel Steward")
        general = await _pack(db, sector, "DGT/HOT/Q0501", "Hotel Steward")
        hits = await search_roles(db, "hotel steward")
        assert [h.slug for h in hits] == [general.slug]
        assert hits[0].variants == 2


class TestAliasTies:
    async def test_a_half_typed_alias_beats_a_literal_prefix(self, db: AsyncSession) -> None:
        """ "war" listed Warper first, because a half-typed alias and a literal
        prefix both score 3.0 and similarity to the pack's name favours the
        literal one every time. Neither title is the other's alias."""
        sector = await _sector(db)
        await _pack(db, sector, "AMH/Q0601", "Warper - Handloom")
        await _pack(db, sector, "HSS/Q0602", "General Duty Assistant")
        db.add(RoleAlias(surface_form="ward boy", job_role="General Duty Assistant"))
        await db.flush()
        hits = await search_roles(db, "war")
        assert [h.job_role for h in hits][:2] == ["General Duty Assistant", "Warper - Handloom"]
        assert hits[0].match_kind == "alias"

    async def test_a_literal_exact_title_still_beats_an_alias_prefix(
        self, db: AsyncSession
    ) -> None:
        """The tie-break only applies to a tie: 4.0 against 3.0 is not one."""
        sector = await _sector(db)
        await _pack(db, sector, "AMH/Q0601", "Ward")
        await _pack(db, sector, "HSS/Q0602", "General Duty Assistant")
        db.add(RoleAlias(surface_form="ward boy", job_role="General Duty Assistant"))
        await db.flush()
        assert (await _roles(db, "ward"))[0] == "Ward"


class TestMultiWordQueries:
    async def test_every_word_in_any_order_finds_the_role(self, db: AsyncSession) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "THC/Q0701", "Waiter - Hotel Services")
        await _pack(db, sector, "THC/Q0702", "Hotel Manager")
        hits = await search_roles(db, "hotel waiter")
        assert [h.job_role for h in hits][0] == "Waiter - Hotel Services"
        assert hits[0].match_kind == "words"
        assert "Hotel Manager" not in [h.job_role for h in hits if h.match_kind == "words"]

    async def test_a_long_title_is_found_where_trigram_matching_is_not_enough(
        self, db: AsyncSession
    ) -> None:
        """ "hotel waiter" against this title has a word similarity of 0.54, under
        the 0.6 threshold, so the trigram branch never admits it. Only the
        all-words condition can: the case the first test cannot tell apart."""
        sector = await _sector(db)
        await _pack(db, sector, "THC/Q0704", "Waiter Trainee for Banquet and Catering at Hotel")
        hits = await search_roles(db, "hotel waiter")
        assert [(h.job_role, h.match_kind) for h in hits] == [
            ("Waiter Trainee for Banquet and Catering at Hotel", "words")
        ]

    async def test_a_stop_word_does_not_have_to_match(self, db: AsyncSession) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "HSS/Q0801", "Ward Assistant")
        assert (await _roles(db, "assistant of the ward"))[0] == "Ward Assistant"

    async def test_a_literal_match_still_outranks_an_all_words_match(
        self, db: AsyncSession
    ) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "THC/Q0701", "Waiter - Hotel Services")
        await _pack(db, sector, "THC/Q0703", "Hotel Waiter Trainee")
        assert (await _roles(db, "hotel waiter"))[0] == "Hotel Waiter Trainee"

    async def test_a_one_word_query_is_unaffected(self, db: AsyncSession) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "THC/Q0701", "Waiter - Hotel Services")
        hits = await search_roles(db, "waiter")
        assert [h.match_kind for h in hits] == ["prefix"]

    def test_the_terms_are_cleaned_of_like_wildcards_and_noise(self) -> None:
        assert _query_terms("hotel waiter") == ["hotel", "waiter"]
        assert _query_terms("the hotel of waiter") == ["hotel", "waiter"]
        assert _query_terms("hotel % waiter") == ["hotel", "waiter"]
        assert _query_terms("hotel _aiter") == ["hotel", "aiter"]
        assert _query_terms("waiter waiter") == []
        assert _query_terms("waiter") == []
        assert _query_terms("%") == []

    def test_a_devanagari_word_is_not_cut_at_its_vowel_signs(self) -> None:
        assert _query_terms("वार्ड बॉय") == ["वार्ड", "बॉय"]


class TestTheAliasChecker:
    """`alias_problems`: what `make check-role-aliases` runs against the real corpus,
    proved here on a fixture corpus because the real one is not in CI."""

    async def test_an_alias_to_a_disability_track_only_role_is_a_failure(
        self, db: AsyncSession
    ) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "PWD/THC/Q2702", "Assistant Chef")
        report = await alias_problems(db, {"cook": "Assistant Chef"})
        assert report.disability_track == [("cook", "Assistant Chef", "PWD/THC/Q2702")]
        assert report.failures

    async def test_the_general_twin_of_a_role_passes(self, db: AsyncSession) -> None:
        """Both kinds of pack under one role name: the representative is the general
        one, so an alias to the role is fine -- which is why the check goes through
        the same representative rule role search uses."""
        sector = await _sector(db)
        # The general code sorts after "PWD/" and has more segments, so neither an
        # alphabetical nor a fewest-segments pick would choose it.
        await _pack(db, sector, "PWD/Q0501", "Hotel Steward")
        await _pack(db, sector, "XYZ/HOT/Q0501", "Hotel Steward")
        report = await alias_problems(db, {"steward": "Hotel Steward"})
        assert report.disability_track == [] and not report.failures

    async def test_a_target_that_names_nothing_is_a_failure(self, db: AsyncSession) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "THC/Q0001", "Real Role")
        report = await alias_problems(db, {"x": "Real Role", "y": "No Such Role"})
        assert report.unresolved == ["no such role"] and report.failures

    async def test_a_key_that_is_a_roles_exact_title_but_aliased_elsewhere_is_a_failure(
        self, db: AsyncSession
    ) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q0901", "Security Analyst")
        await _pack(db, sector, "SSC/Q0902", "Cyber Security Certificate")
        report = await alias_problems(db, {"security analyst": "Cyber Security Certificate"})
        assert report.shadowed == [("security analyst", "security analyst")]
        assert report.failures

    async def test_a_key_aliased_to_its_own_title_is_not_shadowed(self, db: AsyncSession) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q0901", "Security Analyst")
        report = await alias_problems(db, {"security analyst": "Security Analyst"})
        assert report.shadowed == [] and not report.failures

    async def test_a_retired_or_standardless_role_does_not_count_as_a_title(
        self, db: AsyncSession
    ) -> None:
        sector = await _sector(db)
        retired = await _pack(db, sector, "OLD/Q0001", "Old Title")
        retired.is_current = False
        await _pack(db, sector, "THC/Q0002", "Target Role")
        await db.flush()
        report = await alias_problems(db, {"old title": "Target Role"})
        assert report.shadowed == [] and not report.failures

    def test_prefix_collisions_are_reported_and_a_shared_target_is_not_one(self) -> None:
        collisions = alias_prefix_collisions(
            {
                "ward boy": "General Duty Assistant",
                "warehouse": "Warehouse Associate",
                "data entry": "Data Entry",
                "data entry operator": "Data Entry",
            }
        )
        assert collisions["war"] == ["General Duty Assistant", "Warehouse Associate"]
        assert "dat" not in collisions and "data entry" not in collisions

    def test_prefixes_shorter_than_the_minimum_are_not_claims(self) -> None:
        assert "wa" not in alias_prefix_collisions({"ward boy": "A", "warehouse": "B"})

    def test_collisions_are_not_a_failure(self) -> None:
        from api.modules.skills.service import AliasReport

        report = AliasReport([], [], [], {"war": ["A", "B"]})
        assert not report.failures
