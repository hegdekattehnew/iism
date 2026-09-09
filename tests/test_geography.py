"""Geography: the master, and resolving a written place name against it.

This module had no test file at all, and nothing in the suite touched the
`/geography` prefix — despite `resolve_location` being what decides whether a
published listing can be found by location. A job with a NULL `state_id` is
visible at `/jobs` and invisible to `match_jobs(state_id=…)`, which is the
quietest kind of broken.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.nsqf.importer import _DISTRICT_ALIASES
from api.modules.geography import resolve_location
from api.modules.geography.models import District, State
from api.modules.geography.service import DISTRICT_ALIASES


@pytest.fixture
async def master(db: AsyncSession) -> dict[str, object]:
    """A slice of the real master, including the spelling the alias map exists
    for: the corpus says BENGALURU URBAN, an employer writes Bengaluru."""
    karnataka = State(state_code=29, slug="karnataka", name="Karnataka")
    maharashtra = State(state_code=27, slug="maharashtra", name="Maharashtra")
    db.add_all([karnataka, maharashtra])
    await db.flush()

    bengaluru = District(district_code=572, name="BENGALURU URBAN", state_id=karnataka.id)
    pune = District(district_code=521, name="Pune", state_id=maharashtra.id)
    # Eight of the 766 districts carry no name; they are imported by code
    # because the code is still a valid reference.
    unnamed = District(district_code=999, name=None, state_id=karnataka.id)
    db.add_all([bengaluru, pune, unnamed])
    await db.commit()
    return {"karnataka": karnataka, "bengaluru": bengaluru, "pune": pune}


class TestResolvingAPlaceName:
    async def test_an_exact_name_resolves_both_halves(self, db, master) -> None:
        found = await resolve_location(db, "Maharashtra", "Pune")
        assert found.state_id is not None
        assert found.district_id == master["pune"].id

    async def test_matching_ignores_case(self, db, master) -> None:
        assert (await resolve_location(db, "maharashtra", "pune")).state_id is not None

    async def test_the_alias_map_bridges_a_real_spelling(self, db, master) -> None:
        """`Bengaluru` is what an employer writes; `BENGALURU URBAN` is what the
        national master calls it. Without this the seeded Karnataka jobs would
        carry no district."""
        found = await resolve_location(db, "Karnataka", "Bengaluru")
        assert found.district_id == master["bengaluru"].id
        assert (await resolve_location(db, "Karnataka", "Bangalore")).district_id == master[
            "bengaluru"
        ].id

    async def test_an_unresolvable_place_is_not_an_error(self, db, master) -> None:
        """Not every value resolves, and an unresolvable location is still a
        location — which is why the free text sits beside the foreign key rather
        than being replaced by it."""
        found = await resolve_location(db, "Atlantis", "Nowhere")
        assert found.state_id is None and found.district_id is None

    async def test_either_half_can_resolve_alone(self, db, master) -> None:
        assert (await resolve_location(db, "Karnataka", "Nowhere")).state_id is not None
        assert (await resolve_location(db, None, "Pune")).district_id is not None

    async def test_blank_input_resolves_to_nothing(self, db, master) -> None:
        found = await resolve_location(db, "   ", "")
        assert found.state_id is None and found.district_id is None


class TestTheAliasMapsAgree:
    def test_the_two_copies_are_identical(self) -> None:
        """`DISTRICT_ALIASES` exists twice — in the geography service and in the
        NSQF importer, which resolves the same master for rows that predate the
        service. The service's own comment says it is "kept in step with the
        importer's copy"; nothing enforced that until now.
        """
        assert DISTRICT_ALIASES == _DISTRICT_ALIASES


class TestGeographyEndpoints:
    async def test_states_are_listed_alphabetically(self, client: AsyncClient, master) -> None:
        body = (await client.get("/geography/states")).json()
        names = [s["name"] for s in body]
        assert names == sorted(names)
        assert "Karnataka" in names

    async def test_districts_can_be_narrowed_to_one_state(
        self, client: AsyncClient, master
    ) -> None:
        state_id = str(master["karnataka"].id)
        body = (await client.get("/geography/districts", params={"state_id": state_id})).json()
        assert {d["name"] for d in body} == {"BENGALURU URBAN"}

    async def test_unnamed_districts_are_not_offered_as_choices(
        self, client: AsyncClient, master
    ) -> None:
        """They exist in the master and are imported by code, but an unnamed
        option in a dropdown is not a choice anyone can make."""
        body = (await client.get("/geography/districts")).json()
        assert all(d["name"] for d in body)

    async def test_reference_data_needs_no_account(self, client: AsyncClient, master) -> None:
        """The administrative map of India is public information, and a posting
        form that cannot load its own dropdowns is worse than one anybody can
        read."""
        assert (await client.get("/geography/states")).status_code == 200
