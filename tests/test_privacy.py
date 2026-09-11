"""The DPDP Act 2023 rights, as the API delivers them (Sprint 20).

Consent has to be *provable*, so a signup that records nothing is a failure even
when the form showed a checkbox. Erasure has to be *complete*, so every row the
account held is checked by table rather than trusting cascades. Export has to be
*scoped*, so it is checked for someone else's data as much as for the caller's.
"""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.analytics.service import purge_expired
from api.modules.identity import Membership, Tenant, User
from api.modules.marketplace.models import CandidateProfile, Job


def _phone() -> str:
    return "9" + str(uuid.uuid4().int)[:9]


def _email() -> str:
    return f"privacy-{uuid.uuid4().hex[:10]}@example.org"


async def _verify(client: AsyncClient, phone: str, consent: str | None = CONSENT):
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body: dict[str, str] = {"phone": phone, "code": code}
    if consent is not None:
        body["consent_version"] = consent
    return await client.post("/auth/otp/verify", json=body)


async def _candidate(client: AsyncClient) -> tuple[dict[str, str], str]:
    phone = _phone()
    body = (await _verify(client, phone)).json()
    return {"authorization": f"Bearer {body['access_token']}"}, phone


async def _organisation(client: AsyncClient, name: str) -> tuple[dict[str, str], str]:
    address = _email()
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": name,
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/auth/me", headers=headers)).json()
    return headers, me["memberships"][0]["tenant"]["slug"]


# ------------------------------------------------------------------- consent


class TestConsent:
    async def test_a_new_phone_account_needs_consent(self, client: AsyncClient) -> None:
        response = await _verify(client, _phone(), consent=None)
        assert response.status_code == 428
        assert response.json()["detail"] == "consent_required"

    async def test_consent_to_a_superseded_notice_is_not_consent(self, client: AsyncClient) -> None:
        response = await _verify(client, _phone(), consent="2020-01-01")
        assert response.status_code == 428

    async def test_consent_is_recorded_with_its_version_and_time(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        phone = _phone()
        before = datetime.now(UTC)
        assert (await _verify(client, phone)).status_code == 200
        user = await db.scalar(select(User).where(User.phone == "+91" + phone))
        assert user is not None
        assert user.consent_version == CONSENT
        assert user.consented_at is not None and user.consented_at >= before

    async def test_a_wrong_code_is_refused_before_consent_is_mentioned(
        self, client: AsyncClient
    ) -> None:
        """Consent is asked only after the code proves the phone is the caller's.
        Asking first would answer "does this number have an account?" to anyone."""
        phone = _phone()
        await client.post("/auth/otp/request", json={"phone": phone})
        response = await client.post("/auth/otp/verify", json={"phone": phone, "code": "000000"})
        assert response.status_code == 401

    async def test_signing_in_again_needs_no_fresh_consent(self, client: AsyncClient) -> None:
        phone = _phone()
        assert (await _verify(client, phone)).status_code == 200
        assert (await _verify(client, phone, consent=None)).status_code == 200

    async def test_organisation_registration_requires_consent(self, client: AsyncClient) -> None:
        payload = {"email": _email(), "organisation_name": "No Consent Clinic"}
        assert (await client.post("/auth/org/register", json=payload)).status_code == 422
        stale = {**payload, "consent_version": "2020-01-01"}
        assert (await client.post("/auth/org/register", json=stale)).status_code == 422

    async def test_organisation_registration_records_consent(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, _ = await _organisation(client, "Consenting Clinic")
        me = (await client.get("/auth/me", headers=headers)).json()
        assert me["consent_version"] == CONSENT
        user = await db.get(User, uuid.UUID(me["id"]))
        assert user is not None and user.consented_at is not None


# -------------------------------------------------------------------- export


class TestExport:
    async def test_it_holds_the_callers_data_and_nobody_elses(self, client: AsyncClient) -> None:
        headers, phone = await _candidate(client)
        _, other_phone = await _candidate(client)
        await client.put("/me/profile", headers=headers, json={"headline": "Export me"})

        response = await client.get("/me/account/export", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["account"]["phone"] == "+91" + phone
        assert body["account"]["consent_version"] == CONSENT
        assert [m["type"] for m in body["memberships"]] == ["personal"]
        assert body["candidate_profile"]["headline"] == "Export me"
        assert other_phone not in response.text

    async def test_export_does_not_create_a_profile(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Reading what is held must not change what is held."""
        headers, _ = await _organisation(client, "Export Only Clinic")
        body = (await client.get("/me/account/export", headers=headers)).json()
        assert body["candidate_profile"] is None
        user_id = uuid.UUID(body["account"]["id"])
        count = await db.scalar(
            select(func.count())
            .select_from(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
        )
        assert count == 0

    async def test_export_needs_a_signed_in_caller(self, client: AsyncClient) -> None:
        assert (await client.get("/me/account/export")).status_code == 401


# ------------------------------------------------------------------- erasure


class TestDeletion:
    async def test_a_candidate_is_erased_completely(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, phone = await _candidate(client)
        await client.put("/me/profile", headers=headers, json={"headline": "Delete me"})
        me = (await client.get("/auth/me", headers=headers)).json()
        user_id = uuid.UUID(me["id"])
        personal = uuid.UUID(me["memberships"][0]["tenant"]["id"])
        db.add(AnalyticsEvent(name="matches_viewed", user_id=user_id))
        await db.commit()

        preview = (await client.get("/me/account/deletion", headers=headers)).json()
        assert preview == {"organisations_deleted": [], "blocked_by": []}

        assert (await client.delete("/me/account", headers=headers)).status_code == 204

        db.expire_all()
        assert await db.scalar(select(User).where(User.phone == "+91" + phone)) is None
        assert await db.get(Tenant, personal) is None
        for model, column in (
            (CandidateProfile, CandidateProfile.user_id),
            (Membership, Membership.user_id),
            (AnalyticsEvent, AnalyticsEvent.user_id),
        ):
            count = await db.scalar(
                select(func.count()).select_from(model).where(column == user_id)
            )
            assert count == 0, model.__name__

    async def test_the_old_token_stops_working(self, client: AsyncClient) -> None:
        headers, _ = await _candidate(client)
        await client.delete("/me/account", headers=headers)
        assert (await client.get("/auth/me", headers=headers)).status_code == 401

    async def test_a_sole_members_organisation_goes_with_them(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _organisation(client, "Solo Clinic")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        db.add(Job(slug=f"solo-{uuid.uuid4().hex[:6]}", tenant_id=tenant.id, title_en="Nurse"))
        await db.commit()
        tenant_id = tenant.id

        preview = (await client.get("/me/account/deletion", headers=headers)).json()
        assert preview["organisations_deleted"] == [
            {"slug": slug, "name": "Solo Clinic", "listings": 1}
        ]

        assert (await client.delete("/me/account", headers=headers)).status_code == 204
        db.expire_all()
        assert await db.get(Tenant, tenant_id) is None
        jobs = await db.scalar(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id)
        )
        assert jobs == 0

    async def test_the_only_owner_of_a_shared_organisation_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Deleting would leave colleagues in an organisation nobody can
        administer. Refused, with nothing changed, until ownership moves."""
        headers, slug = await _organisation(client, "Shared Clinic")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        colleague = User(email=_email())
        db.add(colleague)
        await db.flush()
        db.add(Membership(user_id=colleague.id, tenant_id=tenant.id, role="member"))
        await db.commit()

        preview = (await client.get("/me/account/deletion", headers=headers)).json()
        assert [o["slug"] for o in preview["blocked_by"]] == [slug]

        response = await client.delete("/me/account", headers=headers)
        assert response.status_code == 409
        assert "Shared Clinic" in response.json()["detail"]
        assert (await client.get("/auth/me", headers=headers)).status_code == 200

    async def test_a_member_who_is_not_the_owner_leaves_the_organisation_standing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        owner_headers, slug = await _organisation(client, "Standing Clinic")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        member_headers, _ = await _candidate(client)
        member_id = uuid.UUID((await client.get("/auth/me", headers=member_headers)).json()["id"])
        db.add(Membership(user_id=member_id, tenant_id=tenant.id, role="member"))
        await db.commit()
        tenant_id = tenant.id

        assert (await client.delete("/me/account", headers=member_headers)).status_code == 204
        db.expire_all()
        assert await db.get(Tenant, tenant_id) is not None
        assert (await client.get("/auth/me", headers=owner_headers)).status_code == 200


# ----------------------------------------------------------------- retention


async def test_retention_removes_old_events_and_keeps_recent_ones(db: AsyncSession) -> None:
    marker = uuid.uuid4()
    # `occurred_at` is a naive `timestamp` column, written by `now()` in UTC.
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add_all(
        [
            AnalyticsEvent(
                name="matches_viewed", subject_id=marker, occurred_at=now - timedelta(days=400)
            ),
            AnalyticsEvent(
                name="matches_viewed", subject_id=marker, occurred_at=now - timedelta(days=10)
            ),
        ]
    )
    await db.commit()

    removed = await purge_expired(db, older_than_days=365)

    assert removed >= 1
    left = (
        await db.scalars(
            select(AnalyticsEvent.occurred_at).where(AnalyticsEvent.subject_id == marker)
        )
    ).all()
    assert len(left) == 1 and left[0] > now - timedelta(days=11)
