"""Deleting one organisation without deleting the account.

**Reported by the owner, 2026-09-23.** A job seeker created two organisations
-- one to hire with, one to offer training -- wanted to get rid of only the
hiring one, and found that the single control on offer deleted their entire
account. The reproduction was worse than the report:

* `DELETE /org/{slug}` returned **405**; the route did not exist.
* `POST /org/{slug}/leave` returned **409** -- "make somebody else an owner
  first" -- which Sprint 25 added on purpose so an organisation is never left
  with nobody in charge, and which a sole owner cannot satisfy without
  inviting a stranger.
* So the only exit was `DELETE /me/account`, which took the account *and* the
  other organisation.

Creating an organisation was one request. Undoing it was impossible. These
tests are the shape of the answer: an owner may delete their organisation, it
takes everything that organisation owns, and it touches **nothing else**.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace.models import Job
from api.modules.notifications.models import Notification


async def _seeker(client: AsyncClient) -> dict[str, str]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _org(client: AsyncClient, headers: dict[str, str], name: str, kind: str) -> str:
    made = await client.post(
        "/me/organisations", headers=headers, json={"organisation_name": name, "tenant_type": kind}
    )
    assert made.status_code == 201, made.text
    return made.json()["slug"]


@pytest.fixture
async def two_organisations(client: AsyncClient) -> dict:
    """The reported setup: one person, one employer, one training provider."""
    headers = await _seeker(client)
    return {
        "headers": headers,
        "employer": await _org(client, headers, "My Hiring Co", "employer"),
        "provider": await _org(client, headers, "My Training Co", "course_provider"),
    }


class TestTheReportedScenario:
    async def test_deleting_one_organisation_leaves_the_account_and_the_other(
        self, two_organisations: dict, client: AsyncClient
    ) -> None:
        h, employer, provider = (
            two_organisations["headers"],
            two_organisations["employer"],
            two_organisations["provider"],
        )

        gone = await client.delete(f"/org/{employer}", headers=h)
        assert gone.status_code == 204

        me = await client.get("/auth/me", headers=h)
        assert me.status_code == 200, "the account must survive"
        slugs = {m["tenant"]["slug"] for m in me.json()["memberships"]}
        assert provider in slugs
        assert employer not in slugs

        assert (await client.get(f"/org/{provider}", headers=h)).status_code == 200
        # 404, not 403: a tenant the caller is not a member of is not news.
        assert (await client.get(f"/org/{employer}", headers=h)).status_code == 404

    async def test_the_preview_says_what_goes_before_anything_does(
        self, two_organisations: dict, client: AsyncClient
    ) -> None:
        h, employer = two_organisations["headers"], two_organisations["employer"]
        preview = await client.get(f"/org/{employer}/deletion", headers=h)
        assert preview.status_code == 200
        body = preview.json()
        assert body["slug"] == employer
        assert body["tenant_type"] == "employer"
        # A sole owner is not "one other member affected".
        assert body["other_members"] == 0

        # And it changed nothing.
        assert (await client.get(f"/org/{employer}", headers=h)).status_code == 200

    async def test_a_sole_owner_can_delete_what_they_cannot_leave(
        self, two_organisations: dict, client: AsyncClient
    ) -> None:
        """The two halves of the trap, in one test.

        `leave` refusing the last owner is correct and stays; what was missing
        was the other door.
        """
        h, employer = two_organisations["headers"], two_organisations["employer"]
        assert (await client.post(f"/org/{employer}/leave", headers=h)).status_code == 409
        assert (await client.delete(f"/org/{employer}", headers=h)).status_code == 204


class TestWhoMay:
    async def test_a_stranger_gets_404_never_403(
        self, two_organisations: dict, client: AsyncClient
    ) -> None:
        outsider = await _seeker(client)
        refused = await client.delete(f"/org/{two_organisations['employer']}", headers=outsider)
        assert refused.status_code == 404

    async def test_anonymous_is_refused(self, two_organisations: dict, client: AsyncClient) -> None:
        assert (await client.delete(f"/org/{two_organisations['employer']}")).status_code == 401

    async def test_a_member_who_is_not_an_owner_cannot_delete_it(
        self, two_organisations: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Deleting is the owner's alone, like `JOB_DELETE` and `ORG_UPDATE`:
        an admin may unpublish, which reverses, and this does not."""
        h, employer = two_organisations["headers"], two_organisations["employer"]
        member_headers = await _seeker(client)
        me = (await client.get("/auth/me", headers=member_headers)).json()
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == employer))
        db.add(Membership(user_id=uuid.UUID(me["id"]), tenant_id=tenant.id, role="admin"))
        await db.commit()

        refused = await client.delete(f"/org/{employer}", headers=member_headers)
        assert refused.status_code == 403, "an admin is a member, so 403 rather than 404"
        assert (await client.delete(f"/org/{employer}", headers=h)).status_code == 204

    async def test_a_personal_workspace_is_not_an_organisation(self, client: AsyncClient) -> None:
        """`_context_for` filters to ORGANISATION_TYPES, so a candidate cannot
        reach their own personal tenant through this route and delete the thing
        their profile hangs off."""
        h = await _seeker(client)
        me = (await client.get("/auth/me", headers=h)).json()
        personal = next(
            m["tenant"]["slug"]
            for m in me["memberships"]
            if m["tenant"]["tenant_type"] == "personal"
        )
        assert (await client.delete(f"/org/{personal}", headers=h)).status_code == 404


class TestWhatGoesWithIt:
    async def test_the_organisations_listings_go_and_nothing_elses_does(
        self, two_organisations: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        h, employer, provider = (
            two_organisations["headers"],
            two_organisations["employer"],
            two_organisations["provider"],
        )
        before = await db.scalar(select(func.count()).select_from(Job))

        await client.delete(f"/org/{employer}", headers=h)

        after = await db.scalar(select(func.count()).select_from(Job))
        assert after == before, "this organisation had no vacancies; nobody else's went"
        assert await db.scalar(select(Tenant).where(Tenant.slug == provider)) is not None

    async def test_applicants_still_waiting_are_told(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A gap recorded since Sprint 24: an organisation could vanish and the
        people waiting on it heard nothing at all."""
        from decimal import Decimal

        from api.modules.marketplace.models import JobSkill
        from api.modules.skills.models import Skill

        h = await _seeker(client)
        employer = await _org(client, h, "Vanishing Co", "employer")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == employer))

        skill = Skill(
            slug="vanishing-standard",
            name="Do the work",
            skill_type="technical",
            nsqf_level=Decimal("4"),
            nos_code="TST/N9101",
            source="nsqf",
        )
        db.add(skill)
        await db.flush()
        job = Job(
            slug="vanishing-role",
            tenant_id=tenant.id,
            title="Vanishing Role",
            status="published",
            employment_type="full_time",
        )
        db.add(job)
        await db.flush()
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=5, is_mandatory=True))
        await db.commit()

        applicant = await _seeker(client)
        applied = await client.post(
            "/me/applications", headers=applicant, json={"job_slug": "vanishing-role"}
        )
        assert applied.status_code == 201

        who = (await client.get("/auth/me", headers=applicant)).json()["id"]
        await client.delete(f"/org/{employer}", headers=h)

        notices = (
            await db.scalars(
                select(Notification).where(
                    Notification.recipient_id == uuid.UUID(who),
                    Notification.template == "vacancy_closed",
                )
            )
        ).all()
        assert len(notices) == 1
        assert notices[0].payload["vacancy"] == "Vanishing Role"
        # The organisation is gone, so the notice must not point at it.
        assert employer not in str(notices[0].payload)

    async def test_the_owners_other_data_survives(
        self, two_organisations: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The whole point of the report: this is not account deletion."""
        h, employer = two_organisations["headers"], two_organisations["employer"]
        me_before = (await client.get("/auth/me", headers=h)).json()

        await client.delete(f"/org/{employer}", headers=h)

        user = await db.get(User, uuid.UUID(me_before["id"]))
        assert user is not None
        assert user.is_active
        # Their personal workspace, which everything candidate-shaped hangs off.
        personal = await db.scalar(
            select(Tenant)
            .join(Membership, Membership.tenant_id == Tenant.id)
            .where(Membership.user_id == user.id, Tenant.tenant_type == "personal")
        )
        assert personal is not None
