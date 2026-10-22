"""Sprint 94 (ADR-102): a training organisation sells courses, delivers training, or both.

One organisation with two capabilities, never two tenants for one real organisation. These tests
hold the four situations the owner named (a seller only, a seller that delivers, a deliverer only,
and an employer, which is neither), the one function that answers what an organisation may do, the
guards on changing it, and the public page it gets.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import CAPABILITIES, capability_for
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import Tenant
from api.modules.skills.hierarchy import Sector
from api.modules.skills.models import Skill
from tests.test_invitations import _accept_as_new_account, _invite


def _email() -> str:
    return f"train-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"


async def _register(
    client: AsyncClient,
    name: str,
    *,
    tenant_type: str = "course_provider",
    sells: bool | None = None,
    delivers: bool | None = None,
) -> tuple[dict[str, str], str]:
    body: dict[str, object] = {
        "email": _email(),
        "organisation_name": name,
        "tenant_type": tenant_type,
        "consent_version": CONSENT,
    }
    if sells is not None:
        body["sells_courses"] = sells
    if delivers is not None:
        body["delivers_training"] = delivers
    requested = await client.post("/auth/org/register", json=body)
    assert requested.status_code == 200, requested.text
    tokens = (
        await client.post(
            "/auth/email/otp/verify",
            json={"email": body["email"], "code": requested.json()["debug_code"]},
        )
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    return headers, tokens["organisation_slug"]


async def _tenant(db: AsyncSession, slug: str) -> Tenant:
    tenant = await db.scalar(
        select(Tenant).where(Tenant.slug == slug).execution_options(populate_existing=True)
    )
    assert tenant is not None
    return tenant


@pytest.fixture
async def sector_skill(db: AsyncSession) -> str:
    sector = Sector(
        sector_ref=f"t-{uuid.uuid4().hex[:6]}",
        name="Healthcare Fixtures",
        slug=f"hf-{uuid.uuid4().hex[:6]}",
    )
    db.add(sector)
    await db.flush()
    skill = Skill(
        slug=f"sector-skill-{uuid.uuid4().hex[:8]}",
        name="A standard in a sector",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code=f"TOR/N{uuid.uuid4().int % 9000 + 1000}",
        source="nsqf",
        sector_id=sector.id,
    )
    db.add(skill)
    await db.commit()
    return skill.slug


async def _publish_course(
    client: AsyncClient, headers: dict[str, str], slug: str, skill: str, title: str
) -> str:
    created = await client.post(
        f"/org/{slug}/courses",
        headers=headers,
        json={"title": title, "skills": [{"skill_slug": skill, "level_taught": 4}]},
    )
    assert created.status_code == 201, created.text
    course = created.json()["slug"]
    published = await client.post(f"/org/{slug}/courses/{course}/publish", headers=headers)
    assert published.status_code == 200, published.text
    return course


class TestTheOneFunctionThatAnswers:
    """`capability_for` is the only place that says what an organisation may do."""

    @pytest.mark.parametrize(
        ("kind", "sells", "delivers", "expected"),
        [
            # seller only: today's provider
            (
                "course_provider",
                True,
                False,
                {"job": False, "course": True, "centre": False, "batch": False},
            ),
            # seller and deliverer: own delivery
            (
                "course_provider",
                True,
                True,
                {"job": False, "course": True, "centre": True, "batch": True},
            ),
            # deliverer only: sells nothing
            (
                "course_provider",
                False,
                True,
                {"job": False, "course": False, "centre": True, "batch": True},
            ),
            # an employer is neither, whatever the flags say
            (
                "employer",
                True,
                True,
                {"job": True, "course": False, "centre": False, "batch": False},
            ),
            # a personal workspace may do nothing
            (
                "personal",
                True,
                True,
                {"job": False, "course": False, "centre": False, "batch": False},
            ),
        ],
    )
    def test_the_four_situations(
        self, kind: str, sells: bool, delivers: bool, expected: dict[str, bool]
    ) -> None:
        tenant = Tenant(
            slug="x",
            name="X",
            tenant_type=kind,
            publishes_courses=sells,
            delivers_training=delivers,
        )
        assert {c: capability_for(tenant, c) for c in CAPABILITIES} == expected

    def test_an_unknown_capability_is_an_error_not_a_no(self) -> None:
        with pytest.raises(ValueError):
            capability_for(Tenant(slug="x", name="X", tenant_type="employer"), "payroll")

    def test_a_new_provider_sells_unless_told_otherwise(self) -> None:
        """Every provider that existed before the capabilities sells courses; the seeds and tests
        that build one directly must not have to know the flag is there."""
        assert Tenant(slug="a", name="A", tenant_type="course_provider").publishes_courses is True
        assert Tenant(slug="b", name="B", tenant_type="employer").publishes_courses is False
        assert Tenant(slug="c", name="C", tenant_type="course_provider").delivers_training is False


class TestRegisteringWithACapability:
    async def test_a_provider_with_no_choice_sells_and_delivers_nothing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register(client, "Default Academy")
        tenant = await _tenant(db, slug)
        assert (tenant.publishes_courses, tenant.delivers_training) == (True, False)

    async def test_a_provider_can_deliver_only(self, client: AsyncClient, db: AsyncSession) -> None:
        _, slug = await _register(client, "Delivery Only Centre", sells=False, delivers=True)
        tenant = await _tenant(db, slug)
        assert (tenant.publishes_courses, tenant.delivers_training) == (False, True)

    async def test_a_provider_can_do_both(self, client: AsyncClient, db: AsyncSession) -> None:
        _, slug = await _register(client, "Both Academy", sells=True, delivers=True)
        tenant = await _tenant(db, slug)
        assert (tenant.publishes_courses, tenant.delivers_training) == (True, True)

    async def test_a_provider_that_does_neither_is_refused(self, client: AsyncClient) -> None:
        refused = await client.post(
            "/auth/org/register",
            json={
                "email": _email(),
                "organisation_name": "Does Nothing Ltd",
                "tenant_type": "course_provider",
                "sells_courses": False,
                "delivers_training": False,
                "consent_version": CONSENT,
            },
        )
        assert refused.status_code == 422

    async def test_an_employer_cannot_deliver_training(self, client: AsyncClient) -> None:
        refused = await client.post(
            "/auth/org/register",
            json={
                "email": _email(),
                "organisation_name": "Hiring Co",
                "tenant_type": "employer",
                "delivers_training": True,
                "consent_version": CONSENT,
            },
        )
        assert refused.status_code == 422

    async def test_an_employer_with_no_choice_has_neither(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register(client, "Plain Employer", tenant_type="employer")
        tenant = await _tenant(db, slug)
        assert (tenant.publishes_courses, tenant.delivers_training) == (False, False)

    async def test_a_signed_in_person_adds_a_delivering_organisation(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The other way in: `POST /me/organisations`, which adds a membership, not an account."""
        headers, _ = await _register(client, "First Org", tenant_type="employer")
        created = await client.post(
            "/me/organisations",
            headers=headers,
            json={
                "organisation_name": "Second Delivery Org",
                "tenant_type": "course_provider",
                "sells_courses": False,
                "delivers_training": True,
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert (body["publishes_courses"], body["delivers_training"]) == (False, True)

    async def test_the_choice_survives_registering_with_an_address_that_already_exists(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """An existing address holds the organisation it asked for until the code proves the
        address is theirs (ADR-038); what the organisation does must be held with it."""
        address = _email()
        first = await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Known Address Org",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
        await client.post(
            "/auth/email/otp/verify", json={"email": address, "code": first.json()["debug_code"]}
        )
        second = await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Held Delivery Academy",
                "tenant_type": "course_provider",
                "sells_courses": False,
                "delivers_training": True,
                "consent_version": CONSENT,
            },
        )
        verified = (
            await client.post(
                "/auth/email/otp/verify",
                json={"email": address, "code": second.json()["debug_code"]},
            )
        ).json()
        tenant = await _tenant(db, verified["organisation_slug"])
        assert tenant.name == "Held Delivery Academy"
        assert (tenant.publishes_courses, tenant.delivers_training) == (False, True)


class TestWhatEachSituationMayDo:
    """The refusal is the capability's, in words, and it is the same gate for every route."""

    async def test_a_deliverer_only_organisation_cannot_create_a_course(
        self, client: AsyncClient
    ) -> None:
        headers, slug = await _register(client, "Delivers Only", sells=False, delivers=True)
        refused = await client.post(
            f"/org/{slug}/courses",
            headers=headers,
            json={"title": "Cannot Sell This", "skills": []},
        )
        assert refused.status_code == 403
        assert "sells courses" in refused.json()["detail"]

    async def test_a_seller_only_organisation_cannot_use_a_delivery_gate(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """No route asks for the `centre` capability yet (centres arrive in Sprint 95), so the
        gate is proved through the dependency itself, with a real tenant and a real owner."""
        from fastapi import HTTPException

        from api.core.authorization import Permission, require

        headers, slug = await _register(client, "Sells Only")
        tenant = await _tenant(db, slug)
        assert not capability_for(tenant, "centre")
        dependency = require(Permission.ORG_READ, "centre")
        me = (await client.get("/auth/me", headers=headers)).json()
        from api.core.authorization import _context_for  # the same resolution the dependency uses
        from api.modules.identity import User

        user = await db.scalar(select(User).where(User.id == uuid.UUID(me["id"])))
        assert user is not None
        # The dependency's own body: resolve the context, then the capability.
        context = await _context_for(db, user, slug)
        with pytest.raises(HTTPException) as refused:
            await dependency(org_slug=slug, db=db, user=user)
        assert refused.value.status_code == 403
        assert "delivers training" in str(refused.value.detail)
        assert context.tenant.slug == slug

    async def test_an_employer_cannot_create_a_course_and_a_seller_cannot_post_a_vacancy(
        self, client: AsyncClient
    ) -> None:
        employer, e_slug = await _register(client, "Employer Co", tenant_type="employer")
        refused = await client.post(
            f"/org/{e_slug}/courses",
            headers=employer,
            json={"title": "Not Ours To Teach", "skills": []},
        )
        assert refused.status_code == 403
        provider, p_slug = await _register(client, "Seller Co")
        refused = await client.post(
            f"/org/{p_slug}/jobs",
            headers=provider,
            json={"title": "Not Ours To Hire", "skills": []},
        )
        assert refused.status_code == 403
        assert "an employer" in refused.json()["detail"]


class TestChangingWhatAnOrganisationDoes:
    async def test_an_owner_adds_delivery_and_it_is_recorded(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _register(client, "Growing Academy")
        changed = await client.put(
            f"/org/{slug}/capabilities", headers=headers, json={"delivers_training": True}
        )
        assert changed.status_code == 200, changed.text
        assert (changed.json()["publishes_courses"], changed.json()["delivers_training"]) == (
            True,
            True,
        )

        events = (
            await db.scalars(
                select(AnalyticsEvent).where(
                    AnalyticsEvent.name == "organisation_capability_changed"
                )
            )
        ).all()
        mine = [e for e in events if e.subject_id == (await _tenant(db, slug)).id]
        assert [e.payload for e in mine] == [{"capability": "delivers_training", "enabled": True}]

    async def test_a_change_that_changes_nothing_records_nothing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, slug = await _register(client, "Steady Academy")
        await client.put(f"/org/{slug}/capabilities", headers=headers, json={"sells_courses": True})
        tenant = await _tenant(db, slug)
        events = (
            await db.scalars(
                select(AnalyticsEvent).where(
                    AnalyticsEvent.name == "organisation_capability_changed",
                    AnalyticsEvent.subject_id == tenant.id,
                )
            )
        ).all()
        assert events == []

    async def test_an_absent_field_leaves_that_capability_alone(self, client: AsyncClient) -> None:
        headers, slug = await _register(client, "Both Stay Academy", sells=True, delivers=True)
        body = (
            await client.put(
                f"/org/{slug}/capabilities", headers=headers, json={"delivers_training": False}
            )
        ).json()
        assert (body["publishes_courses"], body["delivers_training"]) == (True, False)

    async def test_an_organisation_must_do_one_of_them(self, client: AsyncClient) -> None:
        headers, slug = await _register(client, "Must Do Something")
        refused = await client.put(
            f"/org/{slug}/capabilities", headers=headers, json={"sells_courses": False}
        )
        assert refused.status_code == 409
        assert "sells courses, delivers training, or both" in refused.json()["detail"]

    async def test_it_cannot_stop_selling_while_it_has_published_courses(
        self, client: AsyncClient, db: AsyncSession, sector_skill: str
    ) -> None:
        headers, slug = await _register(client, "Selling Academy", sells=True, delivers=True)
        course = await _publish_course(client, headers, slug, sector_skill, "A Live Course")
        refused = await client.put(
            f"/org/{slug}/capabilities", headers=headers, json={"sells_courses": False}
        )
        assert refused.status_code == 409
        assert "published courses" in refused.json()["detail"]
        assert (await _tenant(db, slug)).publishes_courses is True

        # Unpublished, it may stop: a draft is not live work.
        await client.post(f"/org/{slug}/courses/{course}/unpublish", headers=headers)
        allowed = await client.put(
            f"/org/{slug}/capabilities", headers=headers, json={"sells_courses": False}
        )
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["publishes_courses"] is False

    async def test_an_employer_has_no_capabilities_to_change(self, client: AsyncClient) -> None:
        headers, slug = await _register(client, "Hiring Only Co", tenant_type="employer")
        refused = await client.put(
            f"/org/{slug}/capabilities", headers=headers, json={"delivers_training": True}
        )
        assert refused.status_code == 409

    async def test_only_an_owner_may_change_them(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        owner_headers, slug = await _register(client, "Owned Academy")
        address = _email()
        invite = await _invite(client, (owner_headers, slug), address, role="admin")
        admin = await _accept_as_new_account(client, db, invite, address)
        refused = await client.put(
            f"/org/{slug}/capabilities", headers=admin, json={"delivers_training": True}
        )
        assert refused.status_code == 403

    async def test_a_stranger_is_told_nothing_about_the_organisation(
        self, client: AsyncClient
    ) -> None:
        _, slug = await _register(client, "Private Academy")
        stranger, _ = await _register(client, "Other Academy")
        refused = await client.put(
            f"/org/{slug}/capabilities", headers=stranger, json={"delivers_training": True}
        )
        missing = await client.put(
            "/org/no-such-organisation/capabilities",
            headers=stranger,
            json={"delivers_training": True},
        )
        assert refused.status_code == missing.status_code == 404
        assert refused.json() == missing.json()


class TestWhatAnOrganisationSaysAboutItself:
    async def test_the_claims_are_saved_and_read_back_to_members(self, client: AsyncClient) -> None:
        headers, slug = await _register(client, "Claiming Academy")
        saved = await client.put(
            f"/org/{slug}",
            headers=headers,
            json={
                "name": "Claiming Academy",
                "year_established": 1998,
                "affiliations": "NSDC training partner; Healthcare Sector Skill Council",
                "teaching_languages": "Hindi, English",
            },
        )
        assert saved.status_code == 200, saved.text
        body = (await client.get(f"/org/{slug}", headers=headers)).json()
        assert body["year_established"] == 1998
        assert body["affiliations"].startswith("NSDC training partner")
        assert body["teaching_languages"] == "Hindi, English"

    async def test_an_organisation_cannot_be_established_in_the_future(
        self, client: AsyncClient
    ) -> None:
        headers, slug = await _register(client, "Future Academy")
        refused = await client.put(
            f"/org/{slug}",
            headers=headers,
            json={"name": "Future Academy", "year_established": 2999},
        )
        assert refused.status_code == 422

    async def test_a_partial_update_does_not_blank_a_claim(self, client: AsyncClient) -> None:
        headers, slug = await _register(client, "Partial Academy")
        await client.put(
            f"/org/{slug}",
            headers=headers,
            json={"name": "Partial Academy", "affiliations": "NSDC partner"},
        )
        await client.put(f"/org/{slug}", headers=headers, json={"name": "Partial Academy Renamed"})
        body = (await client.get(f"/org/{slug}", headers=headers)).json()
        assert body["affiliations"] == "NSDC partner"
        assert body["name"] == "Partial Academy Renamed"


class TestThePublicPage:
    async def test_it_shows_the_claims_the_derived_sectors_and_the_published_courses(
        self, client: AsyncClient, sector_skill: str
    ) -> None:
        headers, slug = await _register(client, "Page Academy", sells=True, delivers=True)
        await client.put(
            f"/org/{slug}",
            headers=headers,
            json={
                "name": "Page Academy",
                "city": "Pune",
                "description": "We train ward staff.",
                "year_established": 2005,
                "affiliations": "NSDC partner",
                "teaching_languages": "Hindi",
                "contact_email": "private@page-academy.example",
            },
        )
        live = await _publish_course(client, headers, slug, sector_skill, "A Published Course")
        draft = (
            await client.post(
                f"/org/{slug}/courses",
                headers=headers,
                json={"title": "A Draft Course", "skills": []},
            )
        ).json()["slug"]

        response = await client.get(f"/providers/{slug}")
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["name"] == "Page Academy"
        assert (page["publishes_courses"], page["delivers_training"]) == (True, True)
        assert (page["year_established"], page["affiliations"]) == (2005, "NSDC partner")
        assert [c["slug"] for c in page["courses"]] == [live], "a draft is not on the public page"
        assert draft not in [c["slug"] for c in page["courses"]]
        assert page["courses_total"] == 1
        assert page["sectors"] == [{"name": "Healthcare Fixtures", "courses": 1}]
        # The address an organisation did not publish stays unpublished.
        assert "contact_email" not in page
        assert "private@page-academy.example" not in response.text

    async def test_sectors_are_read_from_the_courses_and_leave_with_them(
        self, client: AsyncClient, sector_skill: str
    ) -> None:
        headers, slug = await _register(client, "Moving Academy")
        course = await _publish_course(client, headers, slug, sector_skill, "Course In A Sector")
        assert (await client.get(f"/providers/{slug}")).json()["sectors"] != []
        await client.post(f"/org/{slug}/courses/{course}/unpublish", headers=headers)
        page = (await client.get(f"/providers/{slug}")).json()
        assert page["sectors"] == [], "a sector nobody teaches in any more is not claimed"
        assert page["courses"] == []

    async def test_an_organisation_with_no_courses_still_has_a_page(
        self, client: AsyncClient
    ) -> None:
        _, slug = await _register(client, "Deliverer With Nothing Yet", sells=False, delivers=True)
        page = (await client.get(f"/providers/{slug}")).json()
        assert (page["publishes_courses"], page["delivers_training"]) == (False, True)
        assert (page["courses"], page["sectors"], page["courses_total"]) == ([], [], 0)

    async def test_only_a_training_organisation_has_a_page_and_every_other_slug_is_the_same_404(
        self, client: AsyncClient
    ) -> None:
        _, employer = await _register(client, "An Employer Page", tenant_type="employer")
        employer_404 = await client.get(f"/providers/{employer}")
        missing_404 = await client.get("/providers/no-such-organisation")
        assert employer_404.status_code == missing_404.status_code == 404
        assert employer_404.json() == missing_404.json(), (
            "the answer must not say which slugs exist"
        )


class TestTheServicesDoNotTrustTheirCallers:
    """The routes and schemas refuse these first; the services must refuse them too, because a route
    is only one of the ways in (the pending-organisation hand-off reaches `provision_organisation`
    without a request body) and a race can withdraw the authority a route checked."""

    async def test_provisioning_refuses_an_organisation_that_does_neither(
        self, db: AsyncSession
    ) -> None:
        from fastapi import HTTPException

        from api.modules.identity import User
        from api.modules.identity.service import provision_organisation

        user = User(email=_email())
        db.add(user)
        await db.flush()
        with pytest.raises(HTTPException) as refused:
            await provision_organisation(
                db,
                user,
                "Idle Provisioned Org",
                "course_provider",
                sells_courses=False,
                delivers_training=False,
            )
        assert refused.value.status_code == 422

    async def test_an_employer_provisioned_with_flags_has_neither(self, db: AsyncSession) -> None:
        from api.modules.identity import User
        from api.modules.identity.service import provision_organisation

        user = User(email=_email())
        db.add(user)
        await db.flush()
        tenant = await provision_organisation(
            db, user, "Flagged Employer Org", "employer", sells_courses=True, delivers_training=True
        )
        assert (tenant.publishes_courses, tenant.delivers_training) == (False, False)

    async def test_changing_capabilities_checks_the_actor_is_still_an_owner(
        self, db: AsyncSession
    ) -> None:
        """What the route checked a moment ago may have been withdrawn since (ADR-051)."""
        from fastapi import HTTPException

        from api.modules.identity import Membership, User
        from api.modules.identity.capabilities import set_capabilities

        tenant = Tenant(
            slug=f"own-{uuid.uuid4().hex[:8]}", name="Owner Check", tenant_type="course_provider"
        )
        admin = User(email=_email())
        db.add_all([tenant, admin])
        await db.flush()
        db.add(Membership(user_id=admin.id, tenant_id=tenant.id, role="admin"))
        await db.flush()
        with pytest.raises(HTTPException) as refused:
            await set_capabilities(db, tenant=tenant, actor=admin, delivers_training=True)
        assert refused.value.status_code == 403
        assert "no longer an owner" in str(refused.value.detail)


class TestTheRequestShapes:
    """The schemas refuse what the services would too: the first line of defence, tested alone."""

    @pytest.mark.parametrize("shape", ["register", "create"])
    def test_a_provider_that_does_neither_is_refused(self, shape: str) -> None:
        from pydantic import ValidationError

        from api.modules.identity import schemas

        common = {
            "tenant_type": "course_provider",
            "sells_courses": False,
            "delivers_training": False,
        }
        with pytest.raises(ValidationError):
            if shape == "register":
                schemas.OrgRegisterRequest(
                    email="a@b.example",
                    organisation_name="Idle Org",
                    consent_version=CONSENT,
                    **common,
                )
            else:
                schemas.OrgCreateRequest(organisation_name="Idle Org", **common)

    @pytest.mark.parametrize("shape", ["register", "create"])
    def test_an_employer_that_delivers_is_refused_and_one_that_sells_is_not_asked(
        self, shape: str
    ) -> None:
        from pydantic import ValidationError

        from api.modules.identity import schemas

        def build(**flags: bool):  # type: ignore[no-untyped-def]
            if shape == "register":
                return schemas.OrgRegisterRequest(
                    email="a@b.example",
                    organisation_name="Hiring Org",
                    tenant_type="employer",
                    consent_version=CONSENT,
                    **flags,
                )
            return schemas.OrgCreateRequest(
                organisation_name="Hiring Org", tenant_type="employer", **flags
            )

        with pytest.raises(ValidationError):
            build(delivers_training=True)
        assert build().sells_courses is True  # the neutral default is valid for an employer

    def test_a_year_in_the_future_is_refused_by_the_schema_not_only_by_the_ceiling(self) -> None:
        from datetime import UTC, datetime

        from pydantic import ValidationError

        from api.modules.identity import schemas

        this_year = datetime.now(UTC).year
        assert (
            schemas.OrganisationIn(name="Ok Org", year_established=this_year).year_established
            == this_year
        )
        with pytest.raises(ValidationError):
            schemas.OrganisationIn(name="Ok Org", year_established=this_year + 1)


class TestThePageIsOnlyThisOrganisations:
    async def test_it_lists_its_own_courses_and_never_another_organisations(
        self, client: AsyncClient, sector_skill: str
    ) -> None:
        a_headers, a = await _register(client, "Alpha Training")
        b_headers, b = await _register(client, "Beta Training")
        mine = await _publish_course(client, a_headers, a, sector_skill, "Alpha Only Course")
        theirs = await _publish_course(client, b_headers, b, sector_skill, "Beta Only Course")
        page = (await client.get(f"/providers/{a}")).json()
        assert [c["slug"] for c in page["courses"]] == [mine]
        assert theirs not in [c["slug"] for c in page["courses"]]
        assert page["courses_total"] == 1
        assert page["sectors"] == [{"name": "Healthcare Fixtures", "courses": 1}]
