"""Sprint 12: one identity, many roles — and the authorization that needs.

The load-bearing claim of this sprint is that a person is not an actor type.
The same human can be a candidate looking for work and the owner of the clinic
hiring them, on **one account**. Almost everything here exists to stop that
quietly regressing into two accounts, or into an authorization check somebody
forgot to write.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import ROLE_PERMISSIONS, Permission
from api.core.cache import get_redis
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.geography.models import State
from api.modules.identity import Membership, Tenant
from api.modules.marketplace.models import Job
from api.modules.skills.models import Skill


def _phone() -> str:
    """Unique per test: OTP state lives in Redis, which the rollback fixture
    does not cover, so tests must not share an identifier."""
    return "9" + uuid.uuid4().int.__str__()[:9]


def _email() -> str:
    """An ordinary-looking domain on purpose: `email-validator` rejects the
    reserved `.test` TLD, which is exactly the kind of thing a hand-written
    address regex would have waved through."""
    return f"org-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"


@pytest.fixture
async def seeded_skill_slug(db: AsyncSession) -> str:
    """One NSQF standard to require. The suite runs against an empty container,
    so a job-posting test has to bring its own vocabulary."""
    skill = Skill(
        slug="follow-infection-control-tst-n0001",
        name_en="Follow infection control policies",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N0001",
        source="nsqf",
    )
    db.add(skill)
    await db.commit()
    return skill.slug


@pytest.fixture
async def second_skill_slug(db: AsyncSession) -> str:
    skill = Skill(
        slug="replace-linen-and-make-beds-tst-n0002",
        name_en="Replace linen and make beds",
        skill_type="technical",
        nsqf_level=Decimal("3"),
        nos_code="TST/N0002",
        source="nsqf",
    )
    db.add(skill)
    await db.commit()
    return skill.slug


@pytest.fixture
async def seeded_state(db: AsyncSession) -> str:
    state = State(state_code=27, slug="maharashtra", name="Maharashtra")
    db.add(state)
    await db.commit()
    return state.name


@pytest.fixture(autouse=True)
async def _clear_otp_state():
    yield
    redis = get_redis()
    for pattern in ("auth:otp:*", "auth:refresh:*"):
        keys = [k async for k in redis.scan_iter(match=pattern)]
        if keys:
            await redis.delete(*keys)


async def _headers_for_phone(client: AsyncClient, phone: str | None = None) -> dict[str, str]:
    phone = phone or _phone()
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _register_org(
    client: AsyncClient, name: str, address: str | None = None
) -> tuple[dict[str, str], str]:
    """Register cold, verify, and return (headers, org slug)."""
    address = address or _email()
    requested = await client.post(
        "/auth/org/register",
        json={
            "email": address,
            "organisation_name": name,
            "tenant_type": "employer",
            "consent_version": CONSENT,
        },
    )
    code = requested.json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/auth/me", headers=headers)).json()
    slug = next(m["tenant"]["slug"] for m in me["memberships"] if m["tenant"]["slug"] != "personal")
    return headers, slug


# ------------------------------------------------------- one identity, many roles


class TestOneIdentityManyRoles:
    async def test_a_candidate_can_become_an_employer_without_a_second_account(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The whole point of the sprint. Forking the account here would split a
        person's history and make "signed in with the wrong one" permanent."""
        phone = _phone()
        headers = await _headers_for_phone(client, phone)
        before = (await client.get("/auth/me", headers=headers)).json()

        created = await client.post(
            "/me/organisations",
            headers=headers,
            json={"organisation_name": "Sunrise Clinic", "tenant_type": "employer"},
        )
        assert created.status_code == 201

        after = (await client.get("/auth/me", headers=headers)).json()
        assert after["id"] == before["id"]
        kinds = sorted(m["tenant"]["tenant_type"] for m in after["memberships"])
        assert kinds == ["employer", "personal"]

    async def test_both_surfaces_answer_to_the_same_token(self, client: AsyncClient) -> None:
        headers = await _headers_for_phone(client)
        org = await client.post(
            "/me/organisations",
            headers=headers,
            json={"organisation_name": "Dual Role Co", "tenant_type": "employer"},
        )
        slug = org.json()["slug"]

        # `/me/profile` creates the candidate profile lazily; that is the
        # candidate surface a real user reaches first.
        assert (await client.get("/me/profile", headers=headers)).status_code == 200
        assert (await client.get("/me/matches", headers=headers)).status_code == 200
        assert (await client.get(f"/org/{slug}/jobs", headers=headers)).status_code == 200

    async def test_a_linked_email_signs_in_to_the_same_account(self, client: AsyncClient) -> None:
        headers = await _headers_for_phone(client)
        original = (await client.get("/auth/me", headers=headers)).json()["id"]
        address = _email()

        code = (
            await client.post("/me/credentials/email", headers=headers, json={"email": address})
        ).json()["debug_code"]
        linked = await client.post(
            "/me/credentials/email/verify",
            headers=headers,
            json={"email": address, "code": code},
        )
        assert linked.status_code == 200
        assert linked.json()["email_verified_at"] is not None

        # Sign in again by the *other* credential, and land on the same account.
        code = (await client.post("/auth/email/otp/request", json={"email": address})).json()[
            "debug_code"
        ]
        tokens = (
            await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
        ).json()
        again = await client.get(
            "/auth/me", headers={"authorization": f"Bearer {tokens['access_token']}"}
        )
        assert again.json()["id"] == original

    async def test_an_email_already_on_another_account_is_refused(
        self, client: AsyncClient
    ) -> None:
        """Merging two accounts is a real operation with real consequences for
        profiles and memberships. A login form must not perform one silently."""
        address = _email()
        await _register_org(client, "First Owner", address)

        other = await _headers_for_phone(client)
        code = (
            await client.post("/me/credentials/email", headers=other, json={"email": address})
        ).json()["debug_code"]
        clash = await client.post(
            "/me/credentials/email/verify",
            headers=other,
            json={"email": address, "code": code},
        )
        assert clash.status_code == 409

    async def test_linking_writes_nothing_before_the_code_is_verified(
        self, client: AsyncClient
    ) -> None:
        headers = await _headers_for_phone(client)
        await client.post("/me/credentials/email", headers=headers, json={"email": _email()})

        assert (await client.get("/auth/me", headers=headers)).json()["email"] is None


# ------------------------------------------------------------------ registration


class TestOrganisationRegistration:
    async def test_registering_a_known_address_is_indistinguishable(
        self, client: AsyncClient
    ) -> None:
        """A response that differs by one field is an enumeration oracle. An
        earlier version returned a code for a new address and `null` for a known
        one, which told a prober exactly what it was trying to hide."""
        address = _email()
        payload = {
            "email": address,
            "organisation_name": "Whoever",
            "tenant_type": "employer",
            "consent_version": CONSENT,
        }
        first = await client.post("/auth/org/register", json=payload)
        second = await client.post("/auth/org/register", json=payload)

        assert first.status_code == second.status_code
        assert set(first.json()) == set(second.json())
        assert (first.json()["debug_code"] is None) == (second.json()["debug_code"] is None)

    async def test_registering_twice_creates_one_organisation(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        address = _email()
        for name in ("Real Clinic", "Impostor Clinic"):
            await client.post(
                "/auth/org/register",
                json={
                    "email": address,
                    "organisation_name": name,
                    "tenant_type": "employer",
                    "consent_version": CONSENT,
                },
            )

        assert await db.scalar(select(Tenant).where(Tenant.name == "Impostor Clinic")) is None

    async def test_an_unknown_address_cannot_sign_in(self, client: AsyncClient) -> None:
        """The email path never provisions on first success. An organisation
        carries a tenant and a name, which have to be asked for."""
        address = _email()
        code = (await client.post("/auth/email/otp/request", json={"email": address})).json()[
            "debug_code"
        ]
        assert (
            await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
        ).status_code == 401

    async def test_two_organisations_may_share_a_name(self, client: AsyncClient) -> None:
        _, first = await _register_org(client, "City Hospital")
        _, second = await _register_org(client, "City Hospital")
        assert first != second


# ----------------------------------------------------------------- authorization


class TestAuthorization:
    async def test_a_personal_workspace_is_not_an_organisation(self, client: AsyncClient) -> None:
        """The Sprint 12 regression this suite most needs, because it passed as
        200 before.

        Every candidate is provisioned `owner` of a personal tenant so that
        ADR-010's "a membership from day one" holds. `_context_for` matched on
        membership and slug alone, so that slug resolved as an organisation
        context and `owner` carried JOB_CREATE, JOB_PUBLISH and
        CANDIDATE_SHORTLIST -- letting any candidate read the employer console's
        aggregate pool and publish a vacancy as "Personal workspace".
        """
        headers = await _headers_for_phone(client)
        me = (await client.get("/auth/me", headers=headers)).json()
        personal = next(
            m["tenant"]["slug"]
            for m in me["memberships"]
            if m["tenant"]["tenant_type"] == "personal"
        )

        # 404, not 403: distinguishing "personal workspace" from "no such
        # organisation" would tell a prober which slugs exist.
        assert (await client.get(f"/org/{personal}/jobs", headers=headers)).status_code == 404
        assert (await client.get(f"/org/{personal}/candidates", headers=headers)).status_code == 404
        assert (
            await client.post(
                f"/org/{personal}/jobs",
                headers=headers,
                json={"title_en": "Not from a personal workspace", "skills": []},
            )
        ).status_code == 404

    async def test_a_course_provider_cannot_post_a_vacancy(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Membership answers *may this person act here*, not *is this the right
        kind of organisation*. Both are needed."""
        headers, slug = await _register_org(client, "Skills Academy")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        tenant.tenant_type = "course_provider"
        await db.commit()

        refused = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={"title_en": "Vacancy from a training provider", "skills": []},
        )
        assert refused.status_code == 403

    async def test_one_person_holds_a_different_role_in_each_organisation(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The case that makes per-request tenant resolution matter, and which
        had no coverage at all: the same token must carry different permissions
        depending only on which organisation the request names."""
        headers = await _headers_for_phone(client)
        slugs = []
        for name in ("Northside Clinic", "Southside Clinic"):
            created = await client.post(
                "/me/organisations",
                headers=headers,
                json={"organisation_name": name, "tenant_type": "employer"},
            )
            slugs.append(created.json()["slug"])
        owned, demoted = slugs

        tenant = await db.scalar(select(Tenant).where(Tenant.slug == demoted))
        assert tenant is not None
        membership = await db.scalar(select(Membership).where(Membership.tenant_id == tenant.id))
        assert membership is not None
        membership.role = "member"
        await db.commit()

        body = {"title_en": "Same token, two answers", "skills": []}
        assert (
            await client.post(f"/org/{owned}/jobs", headers=headers, json=body)
        ).status_code == 201
        assert (
            await client.post(f"/org/{demoted}/jobs", headers=headers, json=body)
        ).status_code == 403

    def test_permissions_widen_with_role_and_deletion_is_the_owners_alone(self) -> None:
        member, admin, owner = (ROLE_PERMISSIONS[r] for r in ("member", "admin", "owner"))
        assert member < admin < owner
        assert Permission.JOB_DELETE in owner
        assert Permission.JOB_DELETE not in admin
        # An admin can unpublish, which reverses. Deletion does not.
        assert Permission.JOB_PUBLISH in admin

    async def test_an_organisation_you_do_not_belong_to_is_a_404(self, client: AsyncClient) -> None:
        """404 rather than 403, deliberately: a 403 confirms the organisation
        exists, so an employer could discover a competitor by guessing slugs."""
        _, theirs = await _register_org(client, "Their Clinic")
        mine, _ = await _register_org(client, "My Clinic")

        assert (await client.get(f"/org/{theirs}/jobs", headers=mine)).status_code == 404

    async def test_an_unknown_organisation_answers_identically(self, client: AsyncClient) -> None:
        mine, _ = await _register_org(client, "My Other Clinic")
        assert (await client.get("/org/no-such-org/jobs", headers=mine)).status_code == 404

    async def test_org_routes_require_authentication(self, client: AsyncClient) -> None:
        _, slug = await _register_org(client, "Guarded Clinic")
        assert (await client.get(f"/org/{slug}/jobs")).status_code == 401

    async def test_a_member_may_read_but_not_publish(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _register_org(client, "Demoted Clinic")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        membership = await db.scalar(select(Membership).where(Membership.tenant_id == tenant.id))
        assert membership is not None
        membership.role = "member"
        await db.commit()

        assert (await client.get(f"/org/{slug}/jobs", headers=headers)).status_code == 200
        refused = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={"title_en": "Anything", "skills": []},
        )
        assert refused.status_code == 403


# -------------------------------------------------------------------- publishing


class TestPublishing:
    async def test_a_new_job_is_a_draft_and_invisible_to_candidates(
        self, client: AsyncClient
    ) -> None:
        """`Job.status` defaults to "published" at the model level, so the
        service sets `draft` by hand. Getting that wrong would put an
        unfinished listing straight in front of candidates."""
        headers, slug = await _register_org(client, "Draft Clinic")
        created = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={"title_en": "Quietly Drafted Role", "skills": []},
        )
        assert created.status_code == 201
        assert created.json()["status"] == "draft"

        public = (await client.get("/jobs", params={"limit": 100})).json()
        assert created.json()["slug"] not in [j["slug"] for j in public["items"]]

    async def test_publishing_without_a_standard_is_refused(self, client: AsyncClient) -> None:
        """Matching scores concept overlap, so a job requiring nothing can never
        appear for anyone — it would be published and permanently unmatchable."""
        headers, slug = await _register_org(client, "Empty Clinic")
        job = (
            await client.post(
                f"/org/{slug}/jobs",
                headers=headers,
                json={"title_en": "Requires Nothing", "skills": []},
            )
        ).json()

        refused = await client.post(f"/org/{slug}/jobs/{job['slug']}/publish", headers=headers)
        assert refused.status_code == 422

    async def test_an_unknown_standard_is_rejected_by_name(self, client: AsyncClient) -> None:
        headers, slug = await _register_org(client, "Typo Clinic")
        bad = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={
                "title_en": "Mistyped",
                "skills": [{"skill_slug": "no-such-standard", "importance": 3}],
            },
        )
        assert bad.status_code == 422
        assert "no-such-standard" in bad.json()["detail"]

    async def test_duplicate_standards_merge_on_the_strongest_signal(
        self, client: AsyncClient, db: AsyncSession, seeded_skill_slug: str
    ) -> None:
        """`uq_job_skill` makes a duplicate a constraint violation rather than
        two requirements, and understating either field would weaken a
        requirement the employer actually stated."""
        headers, slug = await _register_org(client, "Merging Clinic")
        created = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={
                "title_en": "Merged Requirements",
                "skills": [
                    {"skill_slug": seeded_skill_slug, "importance": 2, "is_mandatory": False},
                    {"skill_slug": seeded_skill_slug, "importance": 5, "is_mandatory": True},
                ],
            },
        )
        assert created.status_code == 201
        skills = created.json()["skills"]
        assert len(skills) == 1
        assert skills[0]["importance"] == 5
        assert skills[0]["is_mandatory"] is True

    async def test_editing_replaces_the_standards_rather_than_adding_to_them(
        self, client: AsyncClient, seeded_skill_slug: str, second_skill_slug: str
    ) -> None:
        headers, slug = await _register_org(client, "Rewriting Clinic")
        job = (
            await client.post(
                f"/org/{slug}/jobs",
                headers=headers,
                json={
                    "title_en": "Rewritten",
                    "skills": [{"skill_slug": seeded_skill_slug, "importance": 3}],
                },
            )
        ).json()

        updated = await client.put(
            f"/org/{slug}/jobs/{job['slug']}",
            headers=headers,
            json={
                "title_en": "Rewritten",
                "skills": [{"skill_slug": second_skill_slug, "importance": 4}],
            },
        )
        slugs = [s["skill"]["slug"] for s in updated.json()["skills"]]
        assert slugs == [second_skill_slug]

    async def test_a_published_job_reaches_the_public_listing(
        self, client: AsyncClient, seeded_skill_slug: str
    ) -> None:
        headers, slug = await _register_org(client, "Publishing Clinic")
        job = (
            await client.post(
                f"/org/{slug}/jobs",
                headers=headers,
                json={
                    "title_en": "Genuinely Published",
                    "skills": [{"skill_slug": seeded_skill_slug, "importance": 4}],
                },
            )
        ).json()

        published = await client.post(f"/org/{slug}/jobs/{job['slug']}/publish", headers=headers)
        assert published.json()["status"] == "published"

        listed = (await client.get("/jobs", params={"limit": 100})).json()
        assert job["slug"] in [j["slug"] for j in listed["items"]]

    async def test_geography_resolves_on_write(
        self, client: AsyncClient, db: AsyncSession, seeded_state: str
    ) -> None:
        """`state_id` is what `match_jobs(state_id=…)` filters on. Before this,
        it was populated only by the NSQF importer's backfill, so a job posted
        through the API was findable at /jobs and invisible to anyone matching
        on location."""
        headers, slug = await _register_org(client, "Located Clinic")
        created = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={"title_en": "Somewhere Real", "location_state": seeded_state, "skills": []},
        )
        job = await db.scalar(select(Job).where(Job.slug == created.json()["slug"]))
        assert job is not None and job.state_id is not None

    async def test_the_slug_survives_a_title_change(
        self, client: AsyncClient, seeded_skill_slug: str
    ) -> None:
        """A slug is a published URL the moment the job goes live; regenerating
        it on an edit breaks every link to it."""
        headers, slug = await _register_org(client, "Stable Clinic")
        job = (
            await client.post(
                f"/org/{slug}/jobs",
                headers=headers,
                json={"title_en": "Original Title", "skills": []},
            )
        ).json()

        updated = await client.put(
            f"/org/{slug}/jobs/{job['slug']}",
            headers=headers,
            json={"title_en": "Completely Different Title", "skills": []},
        )
        assert updated.json()["slug"] == job["slug"]


# ------------------------------------------------------- the organisation itself


class TestOrganisationProfile:
    async def test_an_owner_can_correct_the_name(self, client: AsyncClient) -> None:
        """There was no tenant update surface at all until now: a name typed
        during registration was permanent."""
        headers, slug = await _register_org(client, "Typo Hosptial")

        updated = await client.put(
            f"/org/{slug}",
            headers=headers,
            json={"name": "Typo Hospital", "description": "We fixed the spelling."},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Typo Hospital"

    async def test_the_slug_does_not_follow_the_name(self, client: AsyncClient) -> None:
        """It is a published URL. Renaming must not break links to the vacancies
        already under it."""
        headers, slug = await _register_org(client, "Original Name")
        await client.put(f"/org/{slug}", headers=headers, json={"name": "Completely Different"})

        assert (await client.get(f"/org/{slug}", headers=headers)).status_code == 200

    async def test_verification_cannot_be_self_asserted(self, client: AsyncClient) -> None:
        """A badge the organisation can set itself is worse than no badge, because
        a candidate reads it as ours."""
        headers, slug = await _register_org(client, "Unverified Clinic")

        await client.put(
            f"/org/{slug}",
            headers=headers,
            json={"name": "Unverified Clinic", "is_verified": True},
        )
        assert (await client.get(f"/org/{slug}", headers=headers)).json()["is_verified"] is False

    async def test_the_contact_address_stays_off_the_public_listing(
        self, client: AsyncClient, seeded_skill_slug: str
    ) -> None:
        """`TenantOut` is embedded in every job and course payload, so a field
        added there is published to whatever scrapes /jobs."""
        headers, slug = await _register_org(client, "Private Inbox Clinic")
        await client.put(
            f"/org/{slug}",
            headers=headers,
            json={"name": "Private Inbox Clinic", "contact_email": "hr@private.example.com"},
        )
        job = (
            await client.post(
                f"/org/{slug}/jobs",
                headers=headers,
                json={
                    "title_en": "Publicly Listed Role",
                    "skills": [{"skill_slug": seeded_skill_slug, "importance": 4}],
                },
            )
        ).json()
        await client.post(f"/org/{slug}/jobs/{job['slug']}/publish", headers=headers)

        public = (await client.get(f"/jobs/{job['slug']}")).json()
        assert "contact_email" not in public["tenant"]
        # The members' view does carry it.
        assert (await client.get(f"/org/{slug}", headers=headers)).json()[
            "contact_email"
        ] == "hr@private.example.com"

    async def test_a_member_cannot_edit_the_organisation(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _register_org(client, "Members Only Clinic")
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        membership = await db.scalar(select(Membership).where(Membership.tenant_id == tenant.id))
        assert membership is not None
        membership.role = "member"
        await db.commit()

        refused = await client.put(f"/org/{slug}", headers=headers, json={"name": "Renamed"})
        assert refused.status_code == 403
        # Reading is still allowed.
        assert (await client.get(f"/org/{slug}", headers=headers)).status_code == 200
