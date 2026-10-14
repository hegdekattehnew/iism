"""An operator enrols an agency's file from the back office (Sprint 61, BL-14.10, ADR-071).

Every rule in `operations/enrolment.py` has a test that fails without it. Set-up goes through the
API the way a person would, and the file is the request body (`text/csv`), as the browser sends it.
"""

import uuid

from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION, get_settings
from api.modules.analytics.models import AnalyticsEvent
from api.modules.geography.models import District, State
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile
from api.modules.operations.models import EnrolmentBatch, EnrolmentBatchMember
from tests.moderation_support import operator, person

HEADER = "phone,full_name,headline,state,district,years_experience\r\n"
P1, P2, P3 = "9830000001", "9830000002", "9830000003"
E1, E2, E3 = "+919830000001", "+919830000002", "+919830000003"
PROGRAMME = "PMKVY-TEST-2026"


def _csv(*rows: str) -> str:
    return HEADER + "".join(r + "\r\n" for r in rows)


async def _geography(db: AsyncSession) -> None:
    n = uuid.uuid4().int % 100000 + 20000
    state = State(state_code=n, slug=f"enrol-state-{n}", name=f"Enrol State {n}")
    db.add(state)
    await db.flush()
    db.add(District(district_code=n, name=f"Enrol District {n}", state_id=state.id))
    await db.flush()
    db.info["place"] = (f"Enrol State {n}", f"Enrol District {n}")


def _place(db: AsyncSession) -> tuple[str, str]:
    return db.info["place"]


async def _post(
    client: AsyncClient,
    headers: dict[str, str],
    step: str,
    body: str,
    *,
    programme: str = PROGRAMME,
    attest: bool | None = None,
) -> Response:
    query = f"programme={programme}"
    if attest is not None:
        query += f"&attest={'true' if attest else 'false'}"
    return await client.post(
        f"/ops/enrolment/{step}?{query}",
        content=body.encode(),
        headers={**headers, "content-type": "text/csv"},
    )


async def _users(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(User)) or 0


async def _by_phone(db: AsyncSession, phone: str) -> User | None:
    return await db.scalar(select(User).where(User.phone == phone))


class TestTheCheck:
    async def test_it_writes_nothing_and_says_what_would_happen(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        await _geography(db)
        state, district = _place(db)
        before = await _users(db)

        body = _csv(
            f"{P1},Anita Kumari,Trainee,{state},{district},1",
            f"{P2},,,,,",
            "12345,Bad Phone,,,,",
        )
        response = await _post(client, admin, "check", body)

        assert response.status_code == 200, response.text
        out = response.json()
        assert out["applied"] is False
        assert (out["new"], out["tag"], out["already"], out["errors"]) == (2, 0, 0, 1)
        assert await _users(db) == before
        assert (await db.scalar(select(func.count()).select_from(EnrolmentBatch))) == 0

    async def test_no_number_is_ever_returned_whole(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        body = _csv(f"{P1},Anita Kumari,,,,", f"{P2},Ravi,,,,")
        response = await _post(client, admin, "check", body)

        assert response.status_code == 200
        for number in (P1, P2, E1, E2):
            assert number not in response.text
        row = response.json()["rows"][0]
        assert row["phone"] == "+9198*****001"
        assert row["first_name"] == "Anita"

    async def test_a_number_twice_in_one_file_is_an_error_on_the_second(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        out = (await _post(client, admin, "check", _csv(f"{P1},A,,,,", "98300 00001,B,,,,"))).json()
        assert [r["status"] for r in out["rows"]] == ["new", "error"]
        assert "same number as row 2" in out["rows"][1]["errors"][0]

    async def test_each_bad_cell_is_an_error_on_its_own_row_and_never_a_500(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        body = _csv(
            "5876543210,Not A Mobile,,,,",  # starts with 5
            f"{P1},Nan Years,,,,nan",
            f"{P2},Too Experienced,,,,61",
            f"{P3},{'x' * 121},,,,",
            "98300000044,Fractional,,,,2.5",
            "9830000005,Fine,,,,3",
        )
        response = await _post(client, admin, "check", body)
        assert response.status_code == 200, response.text
        statuses = [r["status"] for r in response.json()["rows"]]
        assert statuses == ["error", "error", "error", "error", "error", "new"]

    async def test_an_unrecognised_place_is_a_warning_not_an_error(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        out = (await _post(client, admin, "check", _csv(f"{P1},A,,Atlantis,Nowhere,0"))).json()
        row = out["rows"][0]
        assert row["status"] == "new"
        assert len(row["warnings"]) == 2

    async def test_a_file_that_cannot_be_read_is_a_422_with_the_reason(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        missing = await _post(client, admin, "check", "name,headline\r\nA,B\r\n")
        assert missing.status_code == 422
        assert "phone" in missing.json()["detail"]
        empty = await _post(client, admin, "check", "")
        assert empty.status_code == 422
        unnamed = await _post(client, admin, "check", _csv(f"{P1},A,,,,"), programme="x")
        assert unnamed.status_code == 422

    async def test_a_file_over_the_row_cap_is_a_413(
        self, client: AsyncClient, db: AsyncSession, monkeypatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "enrolment_max_rows", 2)
        admin = await operator(client, db, "admin")
        body = _csv(f"{P1},A,,,,", f"{P2},B,,,,", f"{P3},C,,,,")
        assert (await _post(client, admin, "check", body)).status_code == 413


class TestTheApply:
    async def test_without_the_attestation_nothing_is_written(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        before = await _users(db)

        for attest in (None, False):
            response = await _post(client, admin, "apply", _csv(f"{P1},A,,,,"), attest=attest)
            assert response.status_code == 422
            assert "privacy notice" in response.json()["detail"]

        assert await _users(db) == before
        assert (await db.scalar(select(func.count()).select_from(EnrolmentBatch))) == 0

    async def test_a_new_person_gets_an_account_consent_a_profile_and_a_place(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        await _geography(db)
        state, district = _place(db)

        response = await _post(
            client,
            admin,
            "apply",
            _csv(f"{P1},Anita Kumari,Home health aide trainee,{state},{district},2"),
            attest=True,
        )
        assert response.status_code == 200, response.text
        assert response.json()["new"] == 1

        user = await _by_phone(db, E1)
        assert user is not None
        assert user.full_name == "Anita Kumari"
        assert user.consent_version == PRIVACY_NOTICE_VERSION
        assert user.consented_at is not None and user.phone_verified_at is not None
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        )
        assert profile is not None
        assert profile.enrolled_via_programme == PROGRAMME
        assert profile.headline == "Home health aide trainee"
        assert profile.years_experience == 2
        assert profile.state_id is not None and profile.district_id is not None

    async def test_the_batch_records_who_attested_and_what_they_attested_to(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        response = await _post(
            client,
            admin,
            "apply",
            _csv(f"{P1},A,,,,", f"{P2},B,,,,", "bad,C,,,,"),
            attest=True,
        )
        assert response.status_code == 200
        batch = await db.get(EnrolmentBatch, uuid.UUID(response.json()["batch_id"]))
        assert batch is not None
        assert batch.programme == PROGRAMME
        assert batch.attested_notice_version == PRIVACY_NOTICE_VERSION
        assert batch.attested_at is not None and batch.actor_user_id is not None
        assert (batch.created_count, batch.tagged_count, batch.already_count) == (2, 0, 0)
        assert batch.error_count == 1

        members = (
            await db.scalars(
                select(EnrolmentBatchMember).where(EnrolmentBatchMember.batch_id == batch.id)
            )
        ).all()
        assert len(members) == 2 and {m.outcome for m in members} == {"created"}

    async def test_the_second_time_creates_nobody(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        body = _csv(f"{P1},A,,,,", f"{P2},B,,,,")
        await _post(client, admin, "apply", body, attest=True)
        before = await _users(db)

        again = (await _post(client, admin, "apply", body, attest=True)).json()
        assert (again["new"], again["already"]) == (0, 2)
        assert await _users(db) == before

    async def test_someone_who_signed_up_themselves_keeps_everything_and_gains_the_tag(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        user = User(phone=E1, full_name="Their Own Name")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id, headline="My own words", years_experience=9)
        db.add(profile)
        await db.flush()

        out = (
            await _post(
                client, admin, "apply", _csv(f"{P1},Agency Name,Agency headline,,,1"), attest=True
            )
        ).json()
        assert (out["new"], out["tag"]) == (0, 1)

        await db.refresh(user)
        await db.refresh(profile)
        assert user.full_name == "Their Own Name"
        assert profile.headline == "My own words" and profile.years_experience == 9
        assert profile.enrolled_via_programme == PROGRAMME
        member = await db.get(EnrolmentBatchMember, profile.id)
        assert member is not None and member.outcome == "tagged"

    async def test_an_account_with_no_profile_is_given_one_to_carry_the_tag(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        user = User(phone=E1)
        db.add(user)
        await db.flush()

        await _post(client, admin, "apply", _csv(f"{P1},A,,,,"), attest=True)

        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        )
        assert profile is not None and profile.enrolled_via_programme == PROGRAMME

    async def test_someone_already_in_another_programme_is_left_alone_and_named(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        user = User(phone=E1)
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id, enrolled_via_programme="OTHER-PROGRAMME")
        db.add(profile)
        await db.flush()

        # The check says so too: the apply's own guard must not be what makes the promise.
        checked = (await _post(client, admin, "check", _csv(f"{P1},A,,,,"))).json()
        assert checked["rows"][0]["status"] == "already"
        assert "left alone" in checked["rows"][0]["warnings"][0]

        out = (await _post(client, admin, "apply", _csv(f"{P1},A,,,,"), attest=True)).json()
        assert out["already"] == 1
        await db.refresh(profile)
        assert profile.enrolled_via_programme == "OTHER-PROGRAMME"

    async def test_one_bad_row_costs_one_row(self, client: AsyncClient, db: AsyncSession) -> None:
        admin = await operator(client, db, "admin")
        body = _csv(f"{P1},A,,,,", "nope,B,,,,", f"{P2},C,,,,")
        out = (await _post(client, admin, "apply", body, attest=True)).json()
        assert (out["new"], out["errors"]) == (2, 1)
        assert await _by_phone(db, E1) is not None and await _by_phone(db, E2) is not None
        # The failed rows come back as the operator's own file plus an `error` column.
        assert out["errors_csv"].splitlines()[0].endswith(",error")
        assert "nope" in out["errors_csv"]

    async def test_a_number_that_raced_in_is_already_and_the_rest_still_apply(
        self, client: AsyncClient, db: AsyncSession, monkeypatch
    ) -> None:
        """Another request creates the number after this one read the table: the unique
        constraint refuses it inside the row's savepoint, and the loop carries on."""
        from api.modules.operations import enrolment

        admin = await operator(client, db, "admin")
        db.add(User(phone=E1))
        await db.flush()

        async def stale(_db: AsyncSession, _phones: list[str]):
            return {}, {}

        monkeypatch.setattr(enrolment, "_existing", stale)
        out = (
            await _post(client, admin, "apply", _csv(f"{P1},A,,,,", f"{P2},B,,,,"), attest=True)
        ).json()
        assert out["rows"][0]["status"] == "already"
        assert out["rows"][1]["status"] == "new"
        assert await _by_phone(db, E2) is not None

    async def test_the_event_carries_counts_and_no_number(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        await _post(client, admin, "apply", _csv(f"{P1},Anita,,,,"), attest=True)

        event = await db.scalar(
            select(AnalyticsEvent).where(AnalyticsEvent.name == "enrolment_applied")
        )
        assert event is not None
        assert event.payload == {
            "programme": PROGRAMME,
            "created": 1,
            "tagged": 0,
            "already": 0,
            "errors": 0,
        }
        assert P1 not in str(event.payload) and "Anita" not in str(event.payload)


class TestAuthority:
    async def test_support_is_refused_on_every_route_and_nothing_is_written(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        support = await operator(client, db, "support")
        before = await _users(db)

        assert (await client.get("/ops/enrolment/template", headers=support)).status_code == 403
        assert (await client.get("/ops/enrolment/batches", headers=support)).status_code == 403
        for step in ("check", "apply"):
            response = await _post(client, support, step, _csv(f"{P1},A,,,,"), attest=True)
            assert response.status_code == 403
        assert await _users(db) == before

    async def test_a_non_operator_gets_the_unrouted_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, _ = await person(client)
        wrong = await _post(client, headers, "apply", _csv(f"{P1},A,,,,"), attest=True)
        unrouted = await client.get("/ops/definitely-not-a-route", headers=headers)
        assert wrong.status_code == 404 == unrouted.status_code
        assert wrong.json() == unrouted.json()


class TestTheRecord:
    async def test_the_batches_list_shows_who_and_masks_them(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        await _post(client, admin, "apply", _csv(f"{P1},A,,,,"), attest=True)

        batch = await db.scalar(select(EnrolmentBatch))
        assert batch is not None and batch.actor_user_id is not None
        actor = await db.get(User, batch.actor_user_id)
        assert actor is not None
        actor.email = "ops.person@example.org"
        await db.flush()

        batches = (await client.get("/ops/enrolment/batches", headers=admin)).json()["batches"]
        assert batches[0]["programme"] == PROGRAMME
        assert batches[0]["created"] == 1
        assert batches[0]["attested_notice_version"] == PRIVACY_NOTICE_VERSION
        assert batches[0]["operator"] == "op********@example.org"

    async def test_erasing_the_operator_leaves_the_batch_with_no_actor(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        out = (await _post(client, admin, "apply", _csv(f"{P1},A,,,,"), attest=True)).json()
        batch = await db.get(EnrolmentBatch, uuid.UUID(out["batch_id"]))
        assert batch is not None and batch.actor_user_id is not None
        actor = await db.get(User, batch.actor_user_id)
        assert actor is not None

        await db.delete(actor)
        await db.flush()
        await db.refresh(batch)
        assert batch.actor_user_id is None
        assert batch.created_count == 1

    async def test_an_enrolled_person_signs_in_and_their_export_says_how_they_got_here(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        await _post(client, admin, "apply", _csv(f"{P1},Anita Kumari,Trainee,,,0"), attest=True)

        # The account is real: they sign in by code like anybody, with consent already on file.
        code = (await client.post("/auth/otp/request", json={"phone": P1})).json()["debug_code"]
        signed_in = await client.post("/auth/otp/verify", json={"phone": P1, "code": code})
        assert signed_in.status_code == 200, signed_in.text
        headers = {"authorization": f"Bearer {signed_in.json()['access_token']}"}

        export = (await client.get("/me/account/export", headers=headers)).json()
        assert export["candidate_profile"]["headline"] == "Trainee"
        assert export["agency_enrolment"]["programme"] == PROGRAMME
        assert export["agency_enrolment"]["account_created_for_you"] is True
        assert (
            export["agency_enrolment"]["privacy_notice_version_attested"] == PRIVACY_NOTICE_VERSION
        )
        assert "operator" not in str(export["agency_enrolment"]).replace(
            "an operator of this platform, on your behalf", ""
        )

    async def test_the_programme_report_counts_who_was_enrolled(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        await _post(client, admin, "apply", _csv(f"{P1},A,,,,", f"{P2},B,,,,"), attest=True)
        report = (await client.get(f"/ops/programmes/{PROGRAMME}", headers=admin)).json()
        assert report["enrolled"] == 2


class TestTheBody:
    async def test_the_two_enrolment_routes_take_a_spreadsheet_and_nothing_else_does(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A thousand-row agency file is larger than the ordinary request limit (256 KB); the
        enrolment path alone is allowed the upload allowance, as the vacancy upload is."""
        admin = await operator(client, db, "admin")
        padding = "x" * 1500
        big = _csv(*[f"98{n:08d},Person {n},{padding},,,0" for n in range(190)])
        assert len(big) > 256 * 1024, "the fixture must exceed the ordinary limit"

        upload = await _post(client, admin, "check", big)
        ordinary = await client.post("/ops/dashboard", headers=admin, content=b"x" * 300_000)

        assert upload.status_code == 200
        assert ordinary.status_code == 413

    async def test_a_body_past_the_upload_limit_is_413(
        self, client: AsyncClient, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(get_settings(), "max_bulk_body_bytes", 1000)
        admin = await operator(client, db, "admin")
        response = await _post(client, admin, "check", "phone\n" + "9" * 2000)
        assert response.status_code == 413


class TestTheTemplate:
    async def test_it_is_served_by_the_api_with_the_columns(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        admin = await operator(client, db, "admin")
        response = await client.get("/ops/enrolment/template", headers=admin)
        assert response.status_code == 200
        assert response.text.splitlines()[0] == (
            "phone,full_name,headline,state,district,years_experience"
        )
        assert "attachment" in response.headers["content-disposition"]
