"""Geography: the master, and resolving a written place name against it.

This module had no test file at all, and nothing in the suite touched the
`/geography` prefix — despite `resolve_location` being what decides whether a
published listing can be found by location. A job with a NULL `state_id` is
visible at `/jobs` and invisible to `match_jobs(state_id=…)`, which is the
quietest kind of broken.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.nsqf.importer import _DISTRICT_ALIASES
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.geography import resolve_location
from api.modules.geography.models import District, State
from api.modules.geography.service import DISTRICT_ALIASES
from api.modules.marketplace.models import CandidatePreferredLocation, CandidateProfile


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


# ------------------------------------------------------- the candidate's side


async def _auth(client: AsyncClient) -> dict[str, str]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _profile(db: AsyncSession) -> CandidateProfile:
    # The newest profile is the one this test just created through the API.
    return (
        await db.scalars(select(CandidateProfile).order_by(CandidateProfile.created_at.desc()))
    ).first()


class TestAProfileResolvesOnWrite:
    """Sprint 23. `update_profile` was a bare setattr loop and the only writer of
    `CandidateProfile.state_id` was the NSQF importer's backfill -- so every
    profile written through the API had a NULL state, while every *seeded* one
    looked right because the import happened to run afterwards. Location-aware
    matching reads that column; without this it would do nothing, silently."""

    async def test_saving_a_location_resolves_both_halves(
        self, client: AsyncClient, db: AsyncSession, master
    ) -> None:
        headers = await _auth(client)
        await client.put(
            "/me/profile",
            headers=headers,
            json={"location_state": "Karnataka", "location_district": "Bengaluru"},
        )
        profile = await _profile(db)
        assert profile.state_id == master["karnataka"].id
        # Through the alias: the corpus says BENGALURU URBAN.
        assert profile.district_id == master["bengaluru"].id

    async def test_changing_only_the_district_still_resolves_against_the_state_held(
        self, client: AsyncClient, db: AsyncSession, master
    ) -> None:
        headers = await _auth(client)
        await client.put("/me/profile", headers=headers, json={"location_state": "Maharashtra"})
        await client.put("/me/profile", headers=headers, json={"location_district": "Pune"})
        profile = await _profile(db)
        assert profile.state_id is not None
        assert profile.district_id == master["pune"].id

    async def test_an_unknown_place_keeps_its_text_and_resolves_nothing(
        self, client: AsyncClient, db: AsyncSession, master
    ) -> None:
        """An unresolvable place is still a place. The ids sit beside the text,
        never instead of it, and failing to resolve is not an error."""
        headers = await _auth(client)
        response = await client.put(
            "/me/profile",
            headers=headers,
            json={"location_state": "Atlantis", "location_district": "Nowhere"},
        )
        assert response.status_code == 200
        assert response.json()["location_state"] == "Atlantis"
        profile = await _profile(db)
        assert profile.state_id is None and profile.district_id is None

    async def test_a_save_without_location_leaves_it_alone(
        self, client: AsyncClient, db: AsyncSession, master
    ) -> None:
        headers = await _auth(client)
        await client.put("/me/profile", headers=headers, json={"location_state": "Karnataka"})
        await client.put("/me/profile", headers=headers, json={"headline": "Ward attendant"})
        assert (await _profile(db)).state_id == master["karnataka"].id

    async def test_a_preferred_location_resolves_too(
        self, client: AsyncClient, db: AsyncSession, master
    ) -> None:
        headers = await _auth(client)
        response = await client.post(
            "/me/profile/preferred_locations",
            headers=headers,
            json={"state": "Karnataka", "district": "Bengaluru"},
        )
        assert response.status_code == 200
        row = await db.scalar(
            select(CandidatePreferredLocation).where(
                CandidatePreferredLocation.profile_id == (await _profile(db)).id
            )
        )
        assert row.state == "Karnataka"
        assert row.state_id == master["karnataka"].id
        assert row.district_id == master["bengaluru"].id
