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

from api.adapters.nsqf import importer
from api.adapters.nsqf.importer import _backfill_geography
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.geography import resolve_location
from api.modules.geography.models import District, State
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidatePreferredLocation, CandidateProfile


@pytest.fixture
async def master(db: AsyncSession) -> dict[str, object]:
    """A slice of the real master, including the spelling the alias map exists
    for: the corpus says BENGALURU URBAN, an employer writes Bengaluru."""
    karnataka = State(state_code=29, slug="karnataka", name="Karnataka")
    maharashtra = State(state_code=27, slug="maharashtra", name="Maharashtra")
    # Bilaspur is one of exactly three district names the real master gives to
    # two districts each -- with Hamirpur (Himachal / Uttar Pradesh) and
    # Pratapgarh (Rajasthan / Uttar Pradesh). Verified against the imported
    # corpus, not assumed.
    himachal = State(state_code=2, slug="himachal-pradesh", name="Himachal Pradesh")
    chhattisgarh = State(state_code=22, slug="chhattisgarh", name="Chhattisgarh")
    db.add_all([karnataka, maharashtra, himachal, chhattisgarh])
    await db.flush()

    bengaluru = District(district_code=572, name="BENGALURU URBAN", state_id=karnataka.id)
    pune = District(district_code=521, name="Pune", state_id=maharashtra.id)
    # Eight of the 766 districts carry no name; they are imported by code
    # because the code is still a valid reference.
    unnamed = District(district_code=999, name=None, state_id=karnataka.id)
    # Himachal's inserted first deliberately: a lookup that ignores the state
    # returns whichever row Postgres reaches first, so the wrong answer for a
    # Chhattisgarh candidate is the *likely* one rather than a coin flip.
    bilaspur_hp = District(district_code=24, name="Bilaspur", state_id=himachal.id)
    bilaspur_cg = District(district_code=376, name="Bilaspur", state_id=chhattisgarh.id)
    db.add_all([bengaluru, pune, unnamed, bilaspur_hp, bilaspur_cg])
    await db.commit()
    return {
        "karnataka": karnataka,
        "maharashtra": maharashtra,
        "himachal": himachal,
        "chhattisgarh": chhattisgarh,
        "bengaluru": bengaluru,
        "pune": pune,
        "bilaspur_hp": bilaspur_hp,
        "bilaspur_cg": bilaspur_cg,
    }


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


class TestAnAmbiguousDistrictName:
    """Three names in the master belong to two districts each.

    `resolve_location` looked a district up by name with `.limit(1)` and no
    ORDER BY, so "Bilaspur, Chhattisgarh" could carry Himachal's id --
    and `matching._locality` compares ids and nothing else, so it would score
    that vacancy 2, "in your district", for somebody 1,500 km away.
    """

    async def test_the_state_written_beside_it_decides(self, db, master) -> None:
        cg = await resolve_location(db, "Chhattisgarh", "Bilaspur")
        hp = await resolve_location(db, "Himachal Pradesh", "Bilaspur")
        assert cg.district_id == master["bilaspur_cg"].id
        assert hp.district_id == master["bilaspur_hp"].id
        assert cg.district_id != hp.district_id

    async def test_without_a_state_it_resolves_to_nothing(self, db, master) -> None:
        """No id is better than a wrong one. The free text is kept either way,
        so the page still reads correctly; only the unsupportable claim goes."""
        found = await resolve_location(db, None, "Bilaspur")
        assert found.district_id is None

    async def test_a_state_that_does_not_resolve_cannot_disambiguate(self, db, master) -> None:
        found = await resolve_location(db, "Atlantis", "Bilaspur")
        assert found.state_id is None and found.district_id is None

    async def test_an_unambiguous_name_still_resolves_without_a_state(self, db, master) -> None:
        """Only the ambiguous case got stricter. One district bears this name,
        so there is nothing to disambiguate and nothing to refuse."""
        assert (await resolve_location(db, None, "Pune")).district_id == master["pune"].id

    async def test_a_district_in_another_state_is_not_taken(self, db, master) -> None:
        """Pune is in Maharashtra; "Pune, Karnataka" is a contradiction, not a
        Pune. The state resolves and the district deliberately does not."""
        found = await resolve_location(db, "Karnataka", "Pune")
        assert found.state_id == master["karnataka"].id
        assert found.district_id is None

    async def test_an_alias_cannot_reach_across_a_border(self, db, master) -> None:
        """The alias is applied *inside* the state filter. Resolving it first
        and checking the state afterwards would let `Bengaluru` land on
        Karnataka's district while the writer said Maharashtra."""
        found = await resolve_location(db, "Maharashtra", "Bengaluru")
        assert found.state_id == master["maharashtra"].id
        assert found.district_id is None


async def _bare_profile(db: AsyncSession, state: str, district: str, **ids) -> CandidateProfile:
    """A profile with a location and nothing else. `user_id` is NOT NULL, so
    the sweep cannot be exercised without an owning row."""
    user = User(phone=f"+9190000{uuid.uuid4().int % 100000:05d}")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(
        user_id=user.id, location_state=state, location_district=district, **ids
    )
    db.add(profile)
    await db.flush()
    return profile


class TestTheImportBackfill:
    """`_backfill_geography` had no test of any kind, from any angle."""

    def test_the_importer_has_no_resolution_rule_of_its_own(self) -> None:
        """It used to keep a private `_DISTRICT_ALIASES` and a private lookup,
        and a test asserted the two maps were identical -- which kept the
        *letters* in step and not the algorithm. Both now resolve through
        `PlaceIndex`, so there is one map and one rule.
        """
        assert not hasattr(importer, "_DISTRICT_ALIASES")

    async def test_it_corrects_an_id_pointing_at_the_wrong_state(self, db, master) -> None:
        """The sweep's own lookup kept whichever district an unordered SELECT
        returned first, so it could overwrite a correct id with a wrong one.
        Here it has to do the reverse."""
        profile = await _bare_profile(
            db,
            "Chhattisgarh",
            "Bilaspur",
            state_id=master["himachal"].id,
            district_id=master["bilaspur_hp"].id,
        )

        resolved, updated = await _backfill_geography(db)
        assert updated >= 1
        await db.refresh(profile)
        assert profile.district_id == master["bilaspur_cg"].id
        assert resolved >= 1

    async def test_a_second_run_writes_nothing(self, db, master) -> None:
        """`updated_at` is an `onupdate` column, so rewriting identical ids
        still bumps it -- every `make import-nsqf` made every job and every
        candidate profile look freshly edited."""
        await _bare_profile(db, "Maharashtra", "Pune")

        first_resolved, first_updated = await _backfill_geography(db)
        assert first_updated >= 1, "the first run must write, or the second proves nothing"

        second_resolved, second_updated = await _backfill_geography(db)
        assert second_updated == 0
        # Resolution is unchanged; only the writing stopped. The two numbers
        # were one before and are deliberately two now.
        assert second_resolved == first_resolved


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
