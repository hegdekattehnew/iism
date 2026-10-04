"""Role search and abbreviations (Sprint 45, BL-12.14).

Sprint 43 let a synonym ("mfg" -> "manufacturing") *admit* a row into role search
and then scored it as a fuzzy guess. Probing the real corpus found the cost: "mfg
technician" led with "Technician - Mechatronics" and never reached "Pharma
Manufacturing Technician", and "mfg operator" returned Loader Operator, Drone
Operator and Casting Operator, because the synonym only applied to the **whole**
query string and the all-words rule ignored it.

Each test is built so that one rule alone decides the order, as in Sprint 43.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills.service import _term_groups
from tests.test_role_search_trust import _pack, _roles, _sector


class TestTermGroups:
    def test_each_word_with_what_it_may_stand_for(self) -> None:
        assert _term_groups("mfg operator") == [["mfg", "manufacturing"], ["operator"]]

    def test_stop_words_and_repeats_do_not_count(self) -> None:
        assert _term_groups("tech of the lead") == [["tech", "technology"], ["lead"]]

    def test_nothing_when_no_word_has_a_synonym(self) -> None:
        """Without one the rule would repeat the literal all-words rule."""
        assert _term_groups("hotel waiter") == []

    def test_nothing_for_a_single_word(self) -> None:
        assert _term_groups("mfg") == []

    def test_whole_words_only(self) -> None:
        """`it` must not fire inside "credit" -- the reason WORD_SYNONYMS is
        matched on whole words."""
        assert _term_groups("credit officer") == []

    def test_like_wildcards_are_stripped_from_what_is_spliced_into_a_pattern(self) -> None:
        assert _term_groups("mf%g_ operator") == []


class TestSynonymsAreScored:
    async def test_a_phrase_the_synonym_completes_beats_a_fuzzy_guess(
        self, db: AsyncSession
    ) -> None:
        """ "mfg technician": the expanded phrase is *in* the title. Before, it was
        admitted but scored as fuzzy, where a title merely resembling "technician"
        outranked it."""
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q3101", "Technician - Mechatronics")
        await _pack(db, sector, "SSC/Q3102", "Pharma Manufacturing Technician")
        assert (await _roles(db, "mfg technician"))[0] == "Pharma Manufacturing Technician"

    async def test_every_word_may_be_met_by_a_synonym(self, db: AsyncSession) -> None:
        """ "mfg operator": the title carries both words but not the phrase, so only
        the per-word rule finds it. Before, the all-words rule ignored synonyms and
        returned every operator in the corpus."""
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q3201", "Slurry Pump Operator")
        await _pack(db, sector, "SSC/Q3202", "Manufacturing Machine Operator")
        assert (await _roles(db, "mfg operator"))[0] == "Manufacturing Machine Operator"

    async def test_what_was_typed_outranks_what_was_expanded(self, db: AsyncSession) -> None:
        """The discount, at its widest: a title that merely *contains* the typed
        abbreviation beats one that spells it out."""
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q3301", "Manufacturing Helper")
        await _pack(db, sector, "SSC/Q3302", "Assistant Mfg Helper")
        assert await _roles(db, "mfg") == ["Assistant Mfg Helper", "Manufacturing Helper"]

    async def test_all_the_typed_words_outrank_the_expanded_phrase(self, db: AsyncSession) -> None:
        """Both words typed, in the wrong order (1.5), against the phrase the synonym
        completes (1.4): the person's own words win."""
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q3401", "Pharma Manufacturing Technician")
        await _pack(db, sector, "SSC/Q3402", "Technician Mfg Support")
        assert (await _roles(db, "mfg technician"))[:2] == [
            "Technician Mfg Support",
            "Pharma Manufacturing Technician",
        ]

    async def test_the_phrase_outranks_the_words_in_any_order(self, db: AsyncSession) -> None:
        """Between two expanded forms, the contiguous phrase is the better one. The
        looser title is built to look *closer* to the query, so only the tier can
        put the phrase first."""
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q3501", "Technician for Manufacturing")
        await _pack(db, sector, "SSC/Q3502", "Advanced Pharma Manufacturing Technician Skills")
        assert (await _roles(db, "mfg technician"))[0] == (
            "Advanced Pharma Manufacturing Technician Skills"
        )

    async def test_a_role_only_the_synonyms_can_reach_is_admitted(self, db: AsyncSession) -> None:
        """ "mfg tech": "mfg" is nowhere in the title as typed, neither expanded
        phrase ("manufacturing tech", "mfg technology") appears whole in it, and the
        trigram match is too weak to admit it -- so only the per-word rule can."""
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q3601", "Technology Lead for Manufacturing Plants")
        assert await _roles(db, "mfg tech") == ["Technology Lead for Manufacturing Plants"]

    @pytest.mark.parametrize("query", ["hotel waiter", "bank clerk"])
    async def test_a_query_with_no_abbreviation_is_untouched(
        self, db: AsyncSession, query: str
    ) -> None:
        sector = await _sector(db)
        await _pack(db, sector, "SSC/Q3501", "Hotel Waiter")
        await _pack(db, sector, "SSC/Q3502", "Bank Clerk")
        assert (await _roles(db, query))[0] == query.title()
