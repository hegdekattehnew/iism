"""Sprint 18: one identity, honestly.

The product models three kinds of actor and one identity that can hold several
roles. Every defect here was the same defect -- a surface that assumed the
job-seeker case -- and several were found by hand in one sitting because nothing
asserted otherwise. These are the assertions.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity import Tenant, User
from api.modules.marketplace.models import CandidateProfile
from api.modules.skills.models import Skill
from tests.test_organisations import (  # noqa: F401 - autouse fixture registers by import
    _clear_otp_state,
    _email,
    _headers_for_phone,
    _phone,
    _register_org,
)


@pytest.fixture
async def skill_slug(db: AsyncSession) -> str:
    """One standard to require. Local rather than imported from
    `test_organisations`: an imported fixture used as a parameter reads to ruff
    as a redefinition (F811), and silencing that per line hides a real class of
    shadowing bug everywhere else."""
    skill = Skill(
        slug="ward-standard-tst-n9001",
        name_en="Maintain a safe ward environment",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N9001",
        source="nsqf",
    )
    db.add(skill)
    await db.commit()
    return skill.slug


async def _me(client: AsyncClient, headers: dict[str, str]) -> dict:
    return (await client.get("/auth/me", headers=headers)).json()


async def _profiles_for(db: AsyncSession, user_id: str) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(CandidateProfile)
            .where(CandidateProfile.user_id == uuid.UUID(user_id))
        )
    ) or 0


# ------------------------------------------------------------------ the fork


class TestNoSecondAccount:
    """`POST /auth/org/register` minted a fresh `User` for any unfamiliar
    address and ignored who was calling. Sprint 13 documented it in
    `CreateOrgForm.tsx` and removed the button; the route stayed open, and the
    homepage role chooser later put a button back. This is the test that should
    have existed then."""

    async def test_a_signed_in_candidate_gets_a_membership_not_an_account(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _headers_for_phone(client)
        before = await _me(client, headers)
        address = _email()

        response = await client.post(
            "/auth/org/register",
            headers=headers,
            json={
                "email": address,
                "organisation_name": "Fork Test Clinic",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
        assert response.status_code == 200
        body = response.json()
        # No code: the caller is already signed in, so there is nothing to prove.
        assert body["sent"] is False
        assert body["organisation_slug"]

        # One identity. The typed address did not become a second account...
        assert await db.scalar(select(User).where(func.lower(User.email) == address)) is None
        # ...and the organisation is on the account that asked for it.
        after = await _me(client, headers)
        assert after["id"] == before["id"]
        kinds = sorted(m["tenant"]["tenant_type"] for m in after["memberships"])
        assert kinds == ["employer", "personal"]

    async def test_signed_out_registration_is_unchanged(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The guard must not break the path a stranger actually uses."""
        address = _email()
        response = await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Stranger Clinic",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
        assert response.json()["sent"] is True
        assert response.json()["organisation_slug"] is None
        assert await db.scalar(select(User).where(User.email == address)) is not None

    async def test_a_stale_token_counts_as_signed_out(self, client: AsyncClient) -> None:
        """On a public page the honest reading of an expired token is "not
        signed in". Failing a signup form over it would be worse."""
        response = await client.post(
            "/auth/org/register",
            headers={"authorization": "Bearer not-a-real-token"},
            json={
                "email": _email(),
                "organisation_name": "Stale Clinic",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
        assert response.status_code == 200
        assert response.json()["sent"] is True


# ------------------------------------------------- candidate surfaces, gated


class TestOrganisationOnlyAccounts:
    """An organisation-first signup creates no personal tenant. Nothing
    downstream honoured that: `/me/profile` and `/me/matches` created a
    `CandidateProfile` for whoever asked and walked them into the candidate
    onboarding wizard."""

    async def test_the_profile_is_refused_and_nothing_is_created(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, _ = await _register_org(client, "Org Only Clinic")
        me = await _me(client, headers)

        assert (await client.get("/me/profile", headers=headers)).status_code == 403
        assert (await client.get("/me/matches", headers=headers)).status_code == 403
        # The write is what mattered: the refusal happens before `ensure_profile`.
        assert await _profiles_for(db, me["id"]) == 0

    async def test_every_profile_write_is_refused_too(self, client: AsyncClient) -> None:
        headers, _ = await _register_org(client, "Org Only Writer")
        assert (
            await client.put("/me/profile", headers=headers, json={"headline": "x"})
        ).status_code == 403
        assert (
            await client.post("/me/profile/onboarding/complete", headers=headers)
        ).status_code == 403

    async def test_a_candidate_who_also_hires_keeps_their_profile(
        self, client: AsyncClient
    ) -> None:
        """The gate is on the personal membership, not on holding an
        organisation. ADR-038's central case must keep both."""
        headers = await _headers_for_phone(client)
        await client.post(
            "/me/organisations",
            headers=headers,
            json={"organisation_name": "Dual Role Clinic", "tenant_type": "employer"},
        )
        assert (await client.get("/me/profile", headers=headers)).status_code == 200
        assert (await client.get("/me/matches", headers=headers)).status_code == 200


# ------------------------------------------------ registration tells the truth


class TestVerificationSaysWhatHappened:
    """`verify_otp_and_sign_in` computed `created` and the route threw it away,
    so a returning user was dropped into the onboarding wizard. It is safe to
    return on *verify* -- the caller has proved they hold the phone or mailbox --
    and nowhere earlier."""

    async def test_the_first_phone_sign_in_is_new_and_the_second_is_not(
        self, client: AsyncClient
    ) -> None:
        phone = _phone()
        for expected in (True, False):
            code = (await client.post("/auth/otp/request", json={"phone": phone})).json()[
                "debug_code"
            ]
            body = (
                await client.post(
                    "/auth/otp/verify",
                    json={"phone": phone, "code": code, "consent_version": CONSENT},
                )
            ).json()
            assert body["created"] is expected

    async def test_a_new_organisation_account_lands_on_its_organisation(
        self, client: AsyncClient
    ) -> None:
        address = _email()
        code = (
            await client.post(
                "/auth/org/register",
                json={
                    "email": address,
                    "organisation_name": "Landing Clinic",
                    "tenant_type": "employer",
                    "consent_version": CONSENT,
                },
            )
        ).json()["debug_code"]
        body = (
            await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
        ).json()
        assert body["created"] is True
        assert body["organisation_slug"].startswith("landing-clinic")

    async def test_the_request_response_still_says_nothing(self, client: AsyncClient) -> None:
        """The oracle stays shut: at request time a known and an unknown
        address still produce the same keys."""
        address = _email()
        await _register_org(client, "Known Clinic", address)
        payload = {
            "email": address,
            "organisation_name": "Whoever",
            "tenant_type": "employer",
            "consent_version": CONSENT,
        }
        known = await client.post("/auth/org/register", json=payload)
        fresh = await client.post("/auth/org/register", json={**payload, "email": _email()})
        assert set(known.json()) == set(fresh.json())
        assert known.json()["organisation_slug"] is None


class TestTheTypedNameIsNotDiscarded:
    """A known address registering a new organisation used to get a sign-in
    code, have its organisation name silently dropped, and land in whatever
    organisation it already had."""

    async def test_it_is_created_on_the_existing_account_after_verification(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        address = _email()
        headers, first_slug = await _register_org(client, "First Clinic", address)
        owner = (await _me(client, headers))["id"]

        code = (
            await client.post(
                "/auth/org/register",
                json={
                    "email": address,
                    "organisation_name": "Second Clinic",
                    "tenant_type": "course_provider",
                    "consent_version": CONSENT,
                },
            )
        ).json()["debug_code"]
        # Not before the code comes back: provisioning at request time would let
        # anyone who knows an address attach an organisation to someone else.
        assert await db.scalar(select(Tenant).where(Tenant.name == "Second Clinic")) is None

        body = (
            await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
        ).json()
        assert body["created"] is False
        second = await db.scalar(select(Tenant).where(Tenant.name == "Second Clinic"))
        assert second is not None
        assert second.tenant_type == "course_provider"
        assert body["organisation_slug"] == second.slug

        again = await _me(client, {"authorization": f"Bearer {body['access_token']}"})
        assert again["id"] == owner
        assert {m["tenant"]["slug"] for m in again["memberships"]} >= {first_slug, second.slug}


# ------------------------------------------------------------ small correctness


class TestOrganisationProfileEdits:
    async def test_a_partial_update_blanks_nothing(self, client: AsyncClient) -> None:
        """No `exclude_unset`, and a body carrying only a name nulled the
        description, website, logo and contact address."""
        headers, slug = await _register_org(client, "Partial Clinic")
        await client.put(
            f"/org/{slug}",
            headers=headers,
            json={"name": "Partial Clinic", "description": "Ward care since 1998."},
        )
        await client.put(f"/org/{slug}", headers=headers, json={"name": "Renamed Clinic"})

        org = (await client.get(f"/org/{slug}", headers=headers)).json()
        assert org["name"] == "Renamed Clinic"
        assert org["description"] == "Ward care since 1998."


class TestCredentialLinking:
    """The phone half had no test at all, while
    `CredentialsSection.tsx` said it did."""

    async def test_a_linked_phone_signs_in_to_the_same_account(self, client: AsyncClient) -> None:
        headers, _ = await _register_org(client, "Phone Linking Clinic")
        original = (await _me(client, headers))["id"]
        phone = _phone()

        code = (
            await client.post("/me/credentials/phone", headers=headers, json={"phone": phone})
        ).json()["debug_code"]
        linked = await client.post(
            "/me/credentials/phone/verify",
            headers=headers,
            json={"phone": phone, "code": code},
        )
        assert linked.status_code == 200
        assert linked.json()["phone_verified_at"] is not None

        tokens = await _sign_in_by_phone(client, phone)
        again = await _me(client, {"authorization": f"Bearer {tokens['access_token']}"})
        assert again["id"] == original
        # Linking a phone does not make an organisation account a job seeker.
        assert "personal" not in {m["tenant"]["tenant_type"] for m in again["memberships"]}

    async def test_a_phone_already_on_another_account_is_refused(self, client: AsyncClient) -> None:
        phone = _phone()
        await _headers_for_phone(client, phone)
        headers, _ = await _register_org(client, "Clashing Clinic")

        code = (
            await client.post("/me/credentials/phone", headers=headers, json={"phone": phone})
        ).json()["debug_code"]
        clash = await client.post(
            "/me/credentials/phone/verify",
            headers=headers,
            json={"phone": phone, "code": code},
        )
        assert clash.status_code == 409

    async def test_an_email_clash_is_caught_whatever_its_capitalisation(
        self, client: AsyncClient
    ) -> None:
        """`confirm_link` compared case-sensitively while every other email
        lookup did not, so `Org-...@X` walked past the 409 meant for `org-...@x`."""
        address = _email()
        await _register_org(client, "Case Clinic", address)

        other = await _headers_for_phone(client)
        shouted = address.upper()
        code = (
            await client.post("/me/credentials/email", headers=other, json={"email": shouted})
        ).json()["debug_code"]
        clash = await client.post(
            "/me/credentials/email/verify", headers=other, json={"email": shouted, "code": code}
        )
        assert clash.status_code == 409


async def _sign_in_by_phone(client: AsyncClient, phone: str) -> dict:
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    return (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()


# --------------------------------------------------------------- untested routes


async def _published_job(client: AsyncClient, skill_slug: str) -> tuple[dict, str, str]:
    headers, slug = await _register_org(client, f"Hiring {uuid.uuid4().hex[:6]}")
    job = (
        await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={
                "title_en": "Ward Assistant",
                "skills": [{"skill_slug": skill_slug, "importance": 5, "is_mandatory": True}],
            },
        )
    ).json()
    await client.post(f"/org/{slug}/jobs/{job['slug']}/publish", headers=headers)
    return headers, slug, job["slug"]


class TestMatchDetail:
    """`GET /me/matches/{slug}` -- the largest handler in the codebase with no
    test touching it: gap analysis, course suggestions, entry routes."""

    async def test_it_names_the_gap_for_a_published_job(
        self, client: AsyncClient, skill_slug: str
    ) -> None:
        _, _, job_slug = await _published_job(client, skill_slug)
        headers = await _headers_for_phone(client)

        response = await client.get(f"/me/matches/{job_slug}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["job"]["slug"] == job_slug
        # A candidate with no skills is missing the one mandatory standard, and
        # the detail says which -- that naming is the whole point of the page.
        assert body["score"] == 0
        assert [m["is_mandatory"] for m in body["missing"]] == [True]

    async def test_an_unknown_job_is_a_404(self, client: AsyncClient) -> None:
        headers = await _headers_for_phone(client)
        assert (await client.get("/me/matches/no-such-job", headers=headers)).status_code == 404

    async def test_it_is_refused_to_an_organisation_account(
        self, client: AsyncClient, skill_slug: str
    ) -> None:
        headers, _, job_slug = await _published_job(client, skill_slug)
        assert (await client.get(f"/me/matches/{job_slug}", headers=headers)).status_code == 403


class TestTheProductionShortlist:
    """The demo ranking was tested; the authenticated one employers actually
    use, `GET /org/{slug}/candidates/{job_slug}`, was not."""

    async def test_an_employer_can_rank_candidates_for_their_own_job(
        self, client: AsyncClient, skill_slug: str
    ) -> None:
        headers, slug, job_slug = await _published_job(client, skill_slug)
        response = await client.get(f"/org/{slug}/candidates/{job_slug}", headers=headers)
        assert response.status_code == 200

    async def test_someone_elses_organisation_is_a_404(
        self, client: AsyncClient, skill_slug: str
    ) -> None:
        _, slug, job_slug = await _published_job(client, skill_slug)
        stranger, _ = await _register_org(client, "Nosy Clinic")
        assert (
            await client.get(f"/org/{slug}/candidates/{job_slug}", headers=stranger)
        ).status_code == 404
