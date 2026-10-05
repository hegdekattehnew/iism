"""The back office, and the authority that reaches it (ADR-042).

`tenants.is_verified` existed for sixteen sprints with no writer: a column, a
read on the public payload, a read in the interface, and a test asserting it
could not be written. This is the sprint it gained one, and the tests below are
mostly about what that writer must *refuse*.
"""

import uuid
from decimal import Decimal
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import (
    OPERATOR_PERMISSIONS,
    ROLE_PERMISSIONS,
    TIER_PERMISSIONS,
    Permission,
    require_operator,
)
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.applications.models import Application
from api.modules.geography.models import District, State
from api.modules.identity.models import STAFF_TIERS, Tenant, User
from api.modules.marketplace.models import (
    CandidateCertification,
    CandidateProfile,
    CandidateSkill,
    Job,
    JobSkill,
)
from api.modules.notifications import drain
from api.modules.notifications.models import Notification
from api.modules.operations import service
from api.modules.operations.models import TenantVerificationEvent
from api.modules.skills.models import Skill

NOTE = "Registration certificate and GST checked against the register."


def _phone() -> str:
    return f"+9190{uuid.uuid4().int % 100000000:08d}"


def _email() -> str:
    return f"ops-{uuid.uuid4().hex[:10]}@example.com"


async def _candidate(client: AsyncClient) -> dict[str, str]:
    phone = _phone()
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _register_org(client: AsyncClient, name: str) -> tuple[dict[str, str], str]:
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
    slug = next(
        m["tenant"]["slug"] for m in me["memberships"] if m["tenant"]["tenant_type"] != "personal"
    )
    return headers, slug


async def _operator(
    client: AsyncClient, db: AsyncSession, *, tier: str = "admin"
) -> dict[str, str]:
    """An account holding the flag. Granted the way the product grants it --
    `admin` by default so every existing test keeps the unrestricted access
    `is_staff=True` alone used to mean (Sprint 37, BL-7.3)."""
    headers = await _candidate(client)
    me = (await client.get("/auth/me", headers=headers)).json()
    user = await db.get(User, uuid.UUID(me["id"]))
    assert user is not None
    user.is_staff = True
    user.staff_tier = tier
    await db.commit()
    return headers


class TestWhoMayReachTheBackOffice:
    async def test_anonymous_is_401_not_404(self, client: AsyncClient) -> None:
        """401 and 404 are opposite answers and must stay distinguishable.
        `get_current_user` runs first, so "you are signed out" is never
        disguised as "there is nothing here"."""
        assert (await client.get("/ops/organisations")).status_code == 401

    async def test_a_signed_in_stranger_gets_a_plain_404(self, client: AsyncClient) -> None:
        """Byte-identical to an unrouted path. A 403 would confirm they had
        found the back office and that one flag on their row was all that stood
        in the way; a *different* 404 body is just as good an oracle."""
        headers = await _candidate(client)
        refused = await client.get("/ops/organisations", headers=headers)
        unrouted = await client.get("/ops/definitely-not-a-route", headers=headers)
        assert refused.status_code == unrouted.status_code == 404
        assert refused.json() == unrouted.json()

    async def test_an_organisation_owner_cannot_verify_their_own(self, client: AsyncClient) -> None:
        """The escalation case, and the reason `ROLE_PERMISSIONS` may never
        contain an `OPS_` member: `owner` is the widest role there is."""
        headers, slug = await _register_org(client, "Self Serving Ltd")
        refused = await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=headers,
            json={"decision": "granted", "note": NOTE},
        )
        assert refused.status_code == 404

    async def test_an_operator_gets_200_on_the_very_same_url(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """**The non-vacuity guard for every 404 above.** Without it a typo in
        the path would make each of them pass for ever."""
        headers = await _operator(client, db)
        assert (await client.get("/ops/organisations", headers=headers)).status_code == 200

    def test_operator_permissions_are_unreachable_from_any_role(self) -> None:
        granted_by_role: set[Permission] = set()
        for permissions in ROLE_PERMISSIONS.values():
            granted_by_role |= permissions
        # Both non-empty first: an empty set intersects with anything.
        assert granted_by_role
        assert OPERATOR_PERMISSIONS
        assert granted_by_role & OPERATOR_PERMISSIONS == set()

    def test_a_tenant_permission_cannot_be_asked_for_here(self) -> None:
        """At import, not per request: a route asking for the wrong permission
        would otherwise 404 for ever and read as a missing route."""
        with pytest.raises(ValueError, match="not an operator permission"):
            require_operator(Permission.JOB_PUBLISH)

    async def test_no_request_body_anywhere_can_set_is_staff(self, client: AsyncClient) -> None:
        """There is no writer over HTTP, in this or any later revision.

        The scan asserts it **finds** the field on the way out first, so a
        rename cannot make this pass by finding nothing anywhere. Covers
        `staff_tier` too (Sprint 37, BL-7.3) -- the same rule, one tier down.
        """
        schema = (await client.get("/openapi.json")).json()
        components = schema["components"]["schemas"]
        assert "is_staff" in components["UserOut"]["properties"]
        assert "staff_tier" in components["UserOut"]["properties"]

        for name, model in components.items():
            if name.endswith(("In", "Request", "Verify", "Update")):
                assert "is_staff" not in model.get("properties", {}), name
                assert "staff_tier" not in model.get("properties", {}), name


class TestTheQueue:
    async def test_it_excludes_personal_workspaces(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Every candidate owns one, so without the filter the queue would be a
        list of every job seeker on the platform presented as businesses
        awaiting verification. `ORGANISATION_TYPES`' lesson, one query over."""
        await _candidate(client)
        headers = await _operator(client, db)
        body = (await client.get("/ops/organisations", headers=headers)).json()
        assert all(row["tenant_type"] != "personal" for row in body)

    async def test_it_carries_enough_to_decide_on(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """An operator verifying an employer with no vacancies and no members
        is verifying an intention."""
        await _register_org(client, "Countable Ltd")
        headers = await _operator(client, db)
        body = (await client.get("/ops/organisations", headers=headers)).json()
        row = next(r for r in body if r["name"] == "Countable Ltd")
        assert row["members"] == 1
        assert row["jobs"] == 0 and row["courses"] == 0

    async def test_a_verified_organisation_leaves_the_queue(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Departing Ltd")
        headers = await _operator(client, db)
        await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=headers,
            json={"decision": "granted", "note": NOTE},
        )
        body = (await client.get("/ops/organisations", headers=headers)).json()
        assert slug not in [r["slug"] for r in body]


class TestDeciding:
    async def test_granting_records_its_evidence_and_shows_on_the_public_payload(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Verified Ltd")
        headers = await _operator(client, db)

        body = (
            await client.post(
                f"/ops/organisations/{slug}/verification",
                headers=headers,
                json={"decision": "granted", "note": NOTE},
            )
        ).json()
        assert body["is_verified"] is True
        assert body["verified_at"] is not None
        assert body["verification_note"] == NOTE
        assert len(body["history"]) == 1

        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None and tenant.verified_by is not None

    async def test_revoking_clears_the_badge_and_keeps_the_record(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Append-only. The tenant carries the *current* badge's evidence and
        the log carries every decision's -- on revoke the columns go NULL, so
        the reason for a revocation survives only here."""
        _, slug = await _register_org(client, "Revoked Ltd")
        headers = await _operator(client, db)
        for decision in ("granted", "revoked"):
            body = (
                await client.post(
                    f"/ops/organisations/{slug}/verification",
                    headers=headers,
                    json={"decision": decision, "note": f"{decision}: {NOTE}"},
                )
            ).json()

        assert body["is_verified"] is False
        assert body["verified_at"] is None and body["verification_note"] is None
        assert [e["decision"] for e in body["history"]] == ["revoked", "granted"]
        assert "granted" in body["history"][1]["note"]

    async def test_a_badge_without_evidence_is_refused_by_the_api(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Unevidenced Ltd")
        headers = await _operator(client, db)
        for note in ("", "   ", "too short"):
            refused = await client.post(
                f"/ops/organisations/{slug}/verification",
                headers=headers,
                json={"decision": "granted", "note": note},
            )
            assert refused.status_code == 422, note

    async def test_a_badge_without_evidence_is_refused_by_the_database(
        self, db: AsyncSession
    ) -> None:
        """Through the session with a hand-built statement, **never** through
        the API: Pydantic's `min_length` refuses first there, so the constraint
        would never be reached and the test could not fail if it were dropped.
        """
        tenant = Tenant(slug=f"ck-{uuid.uuid4().hex[:8]}", name="Check Ltd", tenant_type="employer")
        db.add(tenant)
        await db.flush()
        with pytest.raises(Exception, match="ck_tenants_verified_has_evidence"):
            await db.execute(
                text("UPDATE tenants SET verified_at = now() WHERE id = :id"),
                {"id": tenant.id},
            )
        await db.rollback()

    async def test_an_unknown_organisation_is_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _operator(client, db)
        refused = await client.post(
            "/ops/organisations/no-such-org/verification",
            headers=headers,
            json={"decision": "granted", "note": NOTE},
        )
        assert refused.status_code == 404


class TestGrantingTheFlag:
    async def test_it_refuses_an_unknown_address_and_creates_nothing(
        self, db: AsyncSession
    ) -> None:
        """A script that can mint an account *and* make it staff is a
        one-command account takeover."""
        address = _email()
        with pytest.raises(LookupError):
            await service.set_staff(db, address=address, staff=True, tier="admin")
        assert await db.scalar(select(User).where(User.email == address)) is None

    async def test_it_grants_and_revokes_an_account_that_exists(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, _ = await _register_org(client, "Roster Ltd")
        me = (await client.get("/auth/me", headers=headers)).json()
        assert me["is_staff"] is False

        await service.set_staff(db, address=me["email"], staff=True, tier="admin")
        assert (await client.get("/auth/me", headers=headers)).json()["is_staff"] is True

        await service.set_staff(db, address=me["email"], staff=False)
        assert (await client.get("/auth/me", headers=headers)).json()["is_staff"] is False

    async def test_the_roster_answers_who_else_holds_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _operator(client, db)
        assert len(await service.staff_roster(db)) >= 1


# ------------------------------------------- Sprint 37, BL-7.3: operator tiers


class TestOperatorTiers:
    """ADR-044: `is_staff` alone answers *is this an operator at all*;
    `staff_tier` answers *which actions*. `support` covers every read-only or
    single-subject decision; only `admin` may grant an organisation's public
    "Verified" badge."""

    def test_admin_is_every_operator_permission_and_a_superset_of_support(self) -> None:
        assert TIER_PERMISSIONS["admin"] == OPERATOR_PERMISSIONS
        assert TIER_PERMISSIONS["support"] < TIER_PERMISSIONS["admin"]

    def test_org_verify_is_reserved_to_admin(self) -> None:
        assert Permission.OPS_ORG_VERIFY not in TIER_PERMISSIONS["support"]
        assert Permission.OPS_ORG_VERIFY in TIER_PERMISSIONS["admin"]

    async def test_a_support_operator_can_read_the_queue(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _operator(client, db, tier="support")
        assert (await client.get("/ops/organisations", headers=headers)).status_code == 200

    async def test_a_support_operator_is_refused_org_verify_with_403_not_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The tier question is not the operator question. They have already
        proven staff standing -- a 404 here would pretend they had not."""
        _, slug = await _register_org(client, "Tier Gated Ltd")
        headers = await _operator(client, db, tier="support")
        refused = await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=headers,
            json={"decision": "granted", "note": NOTE},
        )
        assert refused.status_code == 403

    async def test_a_stranger_gets_404_on_the_very_same_route_a_support_operator_gets_403_on(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The oracle-safety proof: two different refusals, on the same URL,
        distinguishable only by whether staff standing exists at all."""
        _, slug = await _register_org(client, "Oracle Check Ltd")
        stranger = await _candidate(client)
        support = await _operator(client, db, tier="support")

        as_stranger = await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=stranger,
            json={"decision": "granted", "note": NOTE},
        )
        as_support = await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=support,
            json={"decision": "granted", "note": NOTE},
        )
        assert as_stranger.status_code == 404
        assert as_support.status_code == 403
        assert as_stranger.json() != as_support.json()

    async def test_an_admin_operator_can_verify_an_organisation(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Admin Gated Ltd")
        headers = await _operator(client, db, tier="admin")
        granted = await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=headers,
            json={"decision": "granted", "note": NOTE},
        )
        assert granted.status_code == 200

    async def test_a_support_operator_can_still_verify_a_certification(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`OPS_CANDIDATE_VERIFY` is scoped to one person's own evidence, not
        a public badge -- it stays in `support`."""
        headers = await _operator(client, db, tier="support")
        assert (
            await client.get("/ops/candidates/certifications", headers=headers)
        ).status_code == 200


class TestStaffTierIntegrity:
    async def test_granting_without_a_tier_is_refused(self, db: AsyncSession) -> None:
        address = _email()
        db.add(User(email=address, consent_version=CONSENT))
        await db.commit()
        with pytest.raises(ValueError, match="requires a tier"):
            await service.set_staff(db, address=address, staff=True)

    async def test_revoking_clears_the_tier(self, client: AsyncClient, db: AsyncSession) -> None:
        headers, _ = await _register_org(client, "Revoked Operator Ltd")
        me = (await client.get("/auth/me", headers=headers)).json()
        await service.set_staff(db, address=me["email"], staff=True, tier="support")
        await service.set_staff(db, address=me["email"], staff=False)
        user = await db.scalar(select(User).where(User.email == me["email"]))
        assert user is not None
        assert user.is_staff is False
        assert user.staff_tier is None

    async def test_the_database_refuses_staff_with_no_tier(self, db: AsyncSession) -> None:
        user = User(email=_email(), consent_version=CONSENT, is_staff=True, staff_tier=None)
        db.add(user)
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_the_database_refuses_a_tier_on_a_non_operator(self, db: AsyncSession) -> None:
        user = User(email=_email(), consent_version=CONSENT, is_staff=False, staff_tier="admin")
        db.add(user)
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_the_database_refuses_an_unknown_tier(self, db: AsyncSession) -> None:
        user = User(email=_email(), consent_version=CONSENT, is_staff=True, staff_tier="superuser")
        db.add(user)
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_all_named_tiers_are_the_two_documented_ones(self) -> None:
        assert set(STAFF_TIERS) == {"support", "admin"}


class TestDeletingAVerifiedOrganisation:
    async def test_it_leaves_no_verification_history_behind(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The twelfth table `_delete_tenant` knows about. The organisation is
        the *subject* of these rows, so once it is gone they identify nobody --
        and a missing explicit delete would surface as a 500 in the owner's own
        deletion path, which is the kind that ships."""
        owner, slug = await _register_org(client, "Doomed Ltd")
        headers = await _operator(client, db)
        await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=headers,
            json={"decision": "granted", "note": NOTE},
        )
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        tenant_id = tenant.id

        assert (await client.delete(f"/org/{slug}", headers=owner)).status_code == 204

        left = (
            await db.execute(
                select(TenantVerificationEvent).where(
                    TenantVerificationEvent.tenant_id == tenant_id
                )
            )
        ).all()
        assert left == []


class TestEveryOperatorRouteIsGuarded:
    """The residual risk ADR-042 names, pinned structurally.

    `require()`'s own docstring records the failure this prevents: three of
    eight publishing writes shipped without their second guard while
    `CLAUDE.md` asserted all eight had it. A guard a handler must remember is a
    guard that eventually is not there, so this reads the app's own route table
    rather than trusting a review.
    """

    def test_no_ops_route_is_reachable_without_the_dependency(self) -> None:
        from fastapi.routing import APIRoute

        from api.main import app

        # This FastAPI keeps an included router nested rather than flattening
        # its routes into `app.routes`, so walking for `APIRoute` alone finds
        # two of them and would have passed against an unguarded back office.
        def walk(routes):  # type: ignore[no-untyped-def]
            for route in routes:
                if isinstance(route, APIRoute):
                    yield route
                inner = getattr(route, "original_router", None)
                if inner is not None:
                    yield from walk(inner.routes)

        ops = [route for route in walk(app.routes) if route.path.startswith("/ops")]
        # An empty list satisfies `all()`, so the walk has to have walked.
        assert ops, "no /ops routes found -- the assertion below would be vacuous"

        for route in ops:
            names = {
                dependency.call.__qualname__
                for dependency in route.dependant.dependencies
                if dependency.call is not None
            }
            assert any("require_operator" in name for name in names), route.path


# --------------------------------------------- Sprint 33: the programme report


async def _enrolled_candidate(
    db: AsyncSession, *, programme: str | None, skill_id: uuid.UUID | None
) -> CandidateProfile:
    user = User(phone=f"+9193{uuid.uuid4().int % 100000000:08d}")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(user_id=user.id, enrolled_via_programme=programme)
    db.add(profile)
    await db.flush()
    if skill_id is not None:
        db.add(CandidateSkill(profile_id=profile.id, skill_id=skill_id, proficiency=3))
        await db.flush()
    return profile


class TestProgrammeReport:
    """The government-agency actor's thin slice (BL-7.1b). No candidate card,
    no employer-facing payload -- this is an operator viewing an aggregate,
    not a pool of named people, so ADR-037's disclosure rule does not apply
    here the way it does to `candidates_for_job`."""

    async def test_counts_only_the_named_programme(self, db: AsyncSession) -> None:
        skill = Skill(
            slug="programme-report-skill",
            name="Handle programme report records",
            skill_type="technical",
            nsqf_level=Decimal("4"),
            nos_code="TST/N0903",
            source="nsqf",
        )
        tenant = Tenant(
            slug="programme-report-employer", name="Report Hospital", tenant_type="employer"
        )
        db.add_all([skill, tenant])
        await db.flush()
        job = Job(
            slug="programme-report-job", tenant_id=tenant.id, title="Clerk", status="published"
        )
        db.add(job)
        await db.flush()
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=4, is_mandatory=True))
        await db.flush()

        # Enrolled, matches the job, applies, and is hired.
        matched = await _enrolled_candidate(db, programme="PMKVY-TEST", skill_id=skill.id)
        db.add(Application(job_id=job.id, profile_id=matched.id, status="hired"))

        # Enrolled under the same programme, but holds no skill -- no match,
        # no application.
        await _enrolled_candidate(db, programme="PMKVY-TEST", skill_id=None)

        # Enrolled under a *different* programme -- must not be counted at all.
        other_programme = await _enrolled_candidate(
            db, programme="OTHER-PROGRAMME", skill_id=skill.id
        )
        db.add(Application(job_id=job.id, profile_id=other_programme.id, status="hired"))

        # Never enrolled through a programme at all (self-registered).
        await _enrolled_candidate(db, programme=None, skill_id=skill.id)
        await db.commit()

        report = await service.programme_report(db, "PMKVY-TEST")
        assert report.enrolled == 2
        assert report.matched == 1
        assert report.applied == 1
        assert report.hired == 1

    async def test_a_finished_or_absent_gig_worker_was_still_hired(self, db: AsyncSession) -> None:
        """A gig moves `hired` on to `completed` or `no_show`. Both people were
        hired; counting `status == "hired"` alone dropped them from the report."""
        tenant = Tenant(slug="programme-gig-employer", name="Gig Co", tenant_type="employer")
        db.add(tenant)
        await db.flush()
        job = Job(
            slug="programme-gig-job",
            tenant_id=tenant.id,
            title="Shift",
            status="published",
            employment_type="gig",
        )
        db.add(job)
        await db.flush()
        for status in ("completed", "no_show", "rejected"):
            profile = await _enrolled_candidate(db, programme="GIG-PROGRAMME", skill_id=None)
            db.add(Application(job_id=job.id, profile_id=profile.id, status=status))
        await db.commit()

        report = await service.programme_report(db, "GIG-PROGRAMME")
        assert report.applied == 3
        assert report.hired == 2

    async def test_an_unrecognised_programme_reports_zero_not_an_error(
        self, db: AsyncSession
    ) -> None:
        report = await service.programme_report(db, "no-such-programme")
        assert report.enrolled == report.matched == report.applied == report.hired == 0

    async def test_the_route_requires_operator_authority(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        anon = await client.get("/ops/programmes/PMKVY-TEST")
        assert anon.status_code == 401

        stranger = await _candidate(client)
        refused = await client.get("/ops/programmes/PMKVY-TEST", headers=stranger)
        assert refused.status_code == 404

        headers = await _operator(client, db)
        allowed = await client.get("/ops/programmes/PMKVY-TEST", headers=headers)
        assert allowed.status_code == 200
        body = allowed.json()
        assert body["programme"] == "PMKVY-TEST"
        assert set(body) == {"programme", "enrolled", "matched", "applied", "hired"}


class TestKnownProgrammes:
    """A starting point for `programme_report`'s free-text name (Sprint 39,
    BL-10.5), not a second source of truth for what a real programme is."""

    async def test_lists_distinct_named_programmes_only(self, db: AsyncSession) -> None:
        await _enrolled_candidate(db, programme="PMKVY-KNOWN-A", skill_id=None)
        await _enrolled_candidate(db, programme="PMKVY-KNOWN-A", skill_id=None)
        await _enrolled_candidate(db, programme="PMKVY-KNOWN-B", skill_id=None)
        await _enrolled_candidate(db, programme=None, skill_id=None)
        await db.commit()

        names = await service.known_programmes(db)
        assert names.count("PMKVY-KNOWN-A") == 1
        assert "PMKVY-KNOWN-B" in names
        assert None not in names

    async def test_the_route_requires_operator_authority(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        anon = await client.get("/ops/programmes")
        assert anon.status_code == 401

        stranger = await _candidate(client)
        refused = await client.get("/ops/programmes", headers=stranger)
        assert refused.status_code == 404

        headers = await _operator(client, db)
        await _enrolled_candidate(db, programme="PMKVY-ROUTE-TEST", skill_id=None)
        await db.commit()
        allowed = await client.get("/ops/programmes", headers=headers)
        assert allowed.status_code == 200
        assert "PMKVY-ROUTE-TEST" in allowed.json()["programmes"]


class TestProgrammeByDistrict:
    """The one genuinely new query in Sprint 40's dashboard visualisation --
    a separate `GROUP BY` from `programme_report`'s own four numbers."""

    async def test_groups_enrolled_candidates_with_an_unknown_bucket(
        self, db: AsyncSession
    ) -> None:
        state = State(state_code=9101, slug="district-breakdown-state", name="Breakdown State")
        db.add(state)
        await db.flush()
        district = District(district_code=9101, name="Breakdown District", state_id=state.id)
        db.add(district)
        await db.flush()

        placed = await _enrolled_candidate(db, programme="DISTRICT-TEST", skill_id=None)
        placed.district_id = district.id
        unresolved = await _enrolled_candidate(db, programme="DISTRICT-TEST", skill_id=None)
        assert unresolved.district_id is None
        # A different programme's candidate, in the same district, must not
        # be counted here.
        other = await _enrolled_candidate(db, programme="OTHER-DISTRICT-PROGRAMME", skill_id=None)
        other.district_id = district.id
        await db.commit()

        rows = await service.programme_by_district(db, "DISTRICT-TEST")
        # One each: under the minimum, so named and not counted (ADR-057).
        assert {r.district for r in rows} == {"Breakdown District", "Unknown"}
        assert all(r.enrolled is None and r.below_minimum for r in rows)

    async def test_two_districts_with_one_name_stay_two_rows(self, db: AsyncSession) -> None:
        """Grouping on the name merged Bilaspur in two states into one bar. Two
        rows with one label read as a bug, so the state is added to both."""
        first = State(state_code=9111, slug="twin-state-a", name="Twin State A")
        second = State(state_code=9112, slug="twin-state-b", name="Twin State B")
        db.add_all([first, second])
        await db.flush()
        a = District(district_code=9111, name="Twin Town", state_id=first.id)
        b = District(district_code=9112, name="Twin Town", state_id=second.id)
        db.add_all([a, b])
        await db.flush()

        for district, n in ((a, 2), (b, 1)):
            for _ in range(n):
                candidate = await _enrolled_candidate(db, programme="TWIN-TEST", skill_id=None)
                candidate.district_id = district.id
        await db.commit()

        rows = await service.programme_by_district(db, "TWIN-TEST")
        assert {r.district for r in rows} == {
            "Twin Town (Twin State A)",
            "Twin Town (Twin State B)",
        }

    async def _district(
        self, db: AsyncSession, code: int, name: str, programme: str, n: int
    ) -> District:
        state = await db.scalar(select(State).where(State.state_code == 9190))
        if state is None:
            state = State(state_code=9190, slug="small-count-state", name="Small Count State")
            db.add(state)
            await db.flush()
        district = District(district_code=code, name=name, state_id=state.id)
        db.add(district)
        await db.flush()
        for _ in range(n):
            candidate = await _enrolled_candidate(db, programme=programme, skill_id=None)
            candidate.district_id = district.id
        return district

    async def test_a_count_of_one_to_four_is_not_shown_and_five_is(self, db: AsyncSession) -> None:
        for code, n in ((9191, 1), (9192, 4), (9193, 5), (9194, 12)):
            await self._district(db, code, f"District {n}", "SMALL-COUNT", n)
        await db.commit()

        rows = {r.district: r for r in await service.programme_by_district(db, "SMALL-COUNT")}

        assert (rows["District 1"].enrolled, rows["District 1"].below_minimum) == (None, True)
        assert (rows["District 4"].enrolled, rows["District 4"].below_minimum) == (None, True)
        assert (rows["District 5"].enrolled, rows["District 5"].below_minimum) == (5, False)
        assert (rows["District 12"].enrolled, rows["District 12"].below_minimum) == (12, False)

    async def test_rows_are_ranked_on_what_is_shown(self, db: AsyncSession) -> None:
        """A district of one and a district of four, named so the larger sorts *first*
        alphabetically-reversed, must come out in name order: ranked on the true counts, 'Zed'
        (four) would lead 'Alpha' (one) and the order would say which is smaller."""
        await self._district(db, 9195, "Alpha", "RANK-COUNT", 1)
        await self._district(db, 9196, "Zed", "RANK-COUNT", 4)
        await self._district(db, 9197, "Mid", "RANK-COUNT", 6)
        await db.commit()

        rows = await service.programme_by_district(db, "RANK-COUNT")

        assert [r.district for r in rows] == ["Mid", "Alpha", "Zed"]

    async def test_the_route_never_sends_a_hidden_count(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await self._district(db, 9198, "Tiny", "ROUTE-SMALL", 3)
        await db.commit()
        headers = await _operator(client, db, tier="support")

        body = (await client.get("/ops/programmes/ROUTE-SMALL/districts", headers=headers)).json()

        assert body["districts"] == [{"district": "Tiny", "enrolled": None, "below_minimum": True}]
        assert "3" not in str(body["districts"])

    async def test_an_unrecognised_programme_reports_no_rows(self, db: AsyncSession) -> None:
        assert await service.programme_by_district(db, "no-such-programme") == []

    async def test_the_route_requires_operator_authority(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        anon = await client.get("/ops/programmes/PMKVY-TEST/districts")
        assert anon.status_code == 401

        stranger = await _candidate(client)
        refused = await client.get("/ops/programmes/PMKVY-TEST/districts", headers=stranger)
        assert refused.status_code == 404

        headers = await _operator(client, db)
        await _enrolled_candidate(db, programme="PMKVY-DISTRICT-ROUTE", skill_id=None)
        await db.commit()
        allowed = await client.get(
            "/ops/programmes/PMKVY-DISTRICT-ROUTE/districts", headers=headers
        )
        assert allowed.status_code == 200
        body = allowed.json()
        assert body["programme"] == "PMKVY-DISTRICT-ROUTE"
        assert body["minimum_cell"] == 5
        assert body["districts"] == [
            {"district": "Unknown", "enrolled": None, "below_minimum": True}
        ]


class TestPlatformDashboard:
    """An operator's first real landing screen (Sprint 39, BL-10.4)."""

    async def test_counts_match_the_queues_and_platform_totals(self, db: AsyncSession) -> None:
        before = await service.platform_dashboard(db)

        tenant = Tenant(
            slug="dashboard-unverified-employer", name="Dashboard Co", tenant_type="employer"
        )
        db.add(tenant)
        await db.flush()
        job = Job(slug="dashboard-job", tenant_id=tenant.id, title="Clerk", status="published")
        db.add(job)
        profile = await _enrolled_candidate(db, programme=None, skill_id=None)
        cert = CandidateCertification(profile_id=profile.id, name="Dashboard Cert")
        db.add(cert)
        await db.commit()

        after = await service.platform_dashboard(db)
        assert after.unverified_organisations == before.unverified_organisations + 1
        assert after.organisations == before.organisations + 1
        assert after.candidates == before.candidates + 1
        assert after.published_jobs == before.published_jobs + 1
        # No skill named -- unverified_certifications only counts rows naming
        # one, the same filter the queue itself uses.
        assert after.unverified_certifications == before.unverified_certifications

    async def test_includes_scarce_skills_from_the_whole_market(self, db: AsyncSession) -> None:
        """`scarce_skills` (Sprint 40) is `market_scarce_skills()` reused, not
        a second copy of "what counts as demand" (the rule `_scarce_skills`'s
        own docstring states)."""
        skill = Skill(
            slug="ops-dashboard-scarce",
            name="Ops Dashboard Scarce Standard",
            skill_type="technical",
            nsqf_level=Decimal("4"),
            nos_code="OPS/N9001",
            source="nsqf",
        )
        db.add(skill)
        await db.flush()
        tenant = Tenant(
            slug="ops-dashboard-scarce-employer", name="Scarce Co", tenant_type="employer"
        )
        db.add(tenant)
        await db.flush()
        job = Job(
            slug="ops-dashboard-scarce-job",
            tenant_id=tenant.id,
            title="Rare Role",
            status="published",
        )
        db.add(job)
        await db.flush()
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=5, is_mandatory=True))
        await db.commit()

        data = await service.platform_dashboard(db)
        entry = next(s for s in data.scarce_skills if s.nos_code == "OPS/N9001")
        assert entry.required_by == 1
        assert entry.held_by == 0

    async def test_the_route_requires_operator_authority(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        anon = await client.get("/ops/dashboard")
        assert anon.status_code == 401

        stranger = await _candidate(client)
        refused = await client.get("/ops/dashboard", headers=stranger)
        assert refused.status_code == 404

        headers = await _operator(client, db)
        allowed = await client.get("/ops/dashboard", headers=headers)
        assert allowed.status_code == 200
        assert set(allowed.json()) == {
            "unverified_organisations",
            "unverified_certifications",
            "organisations",
            "candidates",
            "published_jobs",
            "published_courses",
            "scarce_skills",
        }


# ---------------------------------------- Sprint 35, BL-3.2: certified evidence

CERT_NOTE = "Certificate number and issuer checked against the SSC's own register."


async def _skill(db: AsyncSession, slug: str) -> Skill:
    skill = Skill(slug=slug, name=slug.replace("-", " ").title(), skill_type="technical")
    db.add(skill)
    await db.flush()
    return skill


async def _add_certification(
    client: AsyncClient, headers: dict[str, str], *, name: str, skill_slug: str | None = None
) -> str:
    """Returns the new certification's id. The generic collection route
    returns the *whole* profile, not the created row -- see
    `profile_routes.py::add_entry` -- so the newest entry is the last one."""
    body = (
        await client.post(
            "/me/profile/certifications",
            headers=headers,
            json={"name": name, "skill_slug": skill_slug},
        )
    ).json()
    return cast(str, body["certifications"][-1]["id"])


class TestCertificationVerification:
    async def test_requires_operator_authority(self, client: AsyncClient) -> None:
        anon = await client.get("/ops/candidates/certifications")
        assert anon.status_code == 401

        stranger = await _candidate(client)
        assert (
            await client.get("/ops/candidates/certifications", headers=stranger)
        ).status_code == 404

    async def test_the_queue_excludes_certifications_naming_no_standard(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _skill(db, "phlebotomy")
        candidate = await _candidate(client)
        await client.post(
            "/me/profile/certifications",
            headers=candidate,
            json={"name": "Untargeted Certificate"},
        )
        headers = await _operator(client, db)
        body = (await client.get("/ops/candidates/certifications", headers=headers)).json()
        assert body == []

    async def test_the_queue_carries_enough_to_decide_on(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _skill(db, "phlebotomy")
        candidate = await _candidate(client)
        await client.post(
            "/me/profile/certifications",
            headers=candidate,
            json={
                "name": "Phlebotomy Technician Certificate",
                "issuing_body": "NSDC",
                "skill_slug": "phlebotomy",
            },
        )
        headers = await _operator(client, db)
        body = (await client.get("/ops/candidates/certifications", headers=headers)).json()
        assert len(body) == 1
        assert body[0]["name"] == "Phlebotomy Technician Certificate"
        assert body[0]["skill_slug"] == "phlebotomy"
        assert body[0]["issuing_body"] == "NSDC"

    async def test_verifying_writes_a_certified_candidate_skill(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _skill(db, "phlebotomy")
        candidate = await _candidate(client)
        cert_id = await _add_certification(
            client, candidate, name="Phlebotomy Technician Certificate", skill_slug="phlebotomy"
        )

        headers = await _operator(client, db)
        body = (
            await client.post(
                f"/ops/candidates/certifications/{cert_id}/verify",
                headers=headers,
                json={"note": CERT_NOTE},
            )
        ).json()
        assert body["skill_slug"] == "phlebotomy"
        assert body["verification_note"] == CERT_NOTE

        me = (await client.get("/auth/me", headers=candidate)).json()
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == uuid.UUID(me["id"]))
        )
        assert profile is not None
        row = await db.scalar(select(CandidateSkill).where(CandidateSkill.profile_id == profile.id))
        assert row is not None
        assert row.source == "certified"

        # Left the queue: it is now verified.
        queue = (await client.get("/ops/candidates/certifications", headers=headers)).json()
        assert cert_id not in [row["id"] for row in queue]

    async def test_editing_a_certification_does_not_unlink_its_standard(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The editor sends back the entry it was given, which carries `skill`
        and not `skill_slug`. Reading that absence as "no standard" silently
        unlinked the standard on every edit -- invisible until the form could
        link one at all."""
        await _skill(db, "edit-keeps-link")
        candidate = await _candidate(client)
        cert_id = await _add_certification(
            client, candidate, name="Ward Care Certificate", skill_slug="edit-keeps-link"
        )

        edited = await client.put(
            f"/me/profile/certifications/{cert_id}",
            headers=candidate,
            json={"name": "Ward Care Certificate (renewed)", "issuing_body": "NSDC"},
        )
        assert edited.status_code == 200
        cert = next(c for c in edited.json()["certifications"] if c["id"] == cert_id)
        assert cert["name"] == "Ward Care Certificate (renewed)"
        assert cert["skill"]["slug"] == "edit-keeps-link"

    async def test_naming_no_standard_on_purpose_does_unlink_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _skill(db, "unlink-on-purpose")
        candidate = await _candidate(client)
        cert_id = await _add_certification(
            client, candidate, name="Certificate", skill_slug="unlink-on-purpose"
        )

        edited = await client.put(
            f"/me/profile/certifications/{cert_id}",
            headers=candidate,
            json={"name": "Certificate", "skill_slug": None},
        )
        cert = next(c for c in edited.json()["certifications"] if c["id"] == cert_id)
        assert cert["skill"] is None

    async def test_changing_the_standard_clears_the_verification(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """An operator verified this credential against one standard. Pointing
        it at another would leave a verified badge on a claim nobody checked."""
        await _skill(db, "verified-standard")
        await _skill(db, "a-different-standard")
        candidate = await _candidate(client)
        cert_id = await _add_certification(
            client, candidate, name="Certificate", skill_slug="verified-standard"
        )
        operator = await _operator(client, db)
        verified = await client.post(
            f"/ops/candidates/certifications/{cert_id}/verify",
            headers=operator,
            json={"note": CERT_NOTE},
        )
        assert verified.status_code == 200

        # Editing without touching the standard keeps the verification.
        await client.put(
            f"/me/profile/certifications/{cert_id}",
            headers=candidate,
            json={"name": "Certificate, renamed"},
        )
        db.expire_all()
        row = await db.get(CandidateCertification, uuid.UUID(cert_id))
        assert row is not None and row.verified_at is not None

        # Pointing it at a different standard does not.
        await client.put(
            f"/me/profile/certifications/{cert_id}",
            headers=candidate,
            json={"name": "Certificate, renamed", "skill_slug": "a-different-standard"},
        )
        db.expire_all()
        row = await db.get(CandidateCertification, uuid.UUID(cert_id))
        assert row is not None
        assert row.verified_at is None and row.verified_by is None
        assert row.verification_note is None

        # ...and it is back in the queue for somebody to check against the new one.
        queue = (await client.get("/ops/candidates/certifications", headers=operator)).json()
        assert cert_id in [r["id"] for r in queue]

    async def test_a_certification_naming_no_standard_cannot_be_verified(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        candidate = await _candidate(client)
        cert_id = await _add_certification(client, candidate, name="Untargeted Certificate")

        headers = await _operator(client, db)
        refused = await client.post(
            f"/ops/candidates/certifications/{cert_id}/verify",
            headers=headers,
            json={"note": CERT_NOTE},
        )
        assert refused.status_code == 400

    async def test_an_unknown_certification_is_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _operator(client, db)
        missing = await client.post(
            f"/ops/candidates/certifications/{uuid.uuid4()}/verify",
            headers=headers,
            json={"note": CERT_NOTE},
        )
        assert missing.status_code == 404

    async def test_evidence_shorter_than_ten_characters_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _skill(db, "phlebotomy")
        candidate = await _candidate(client)
        cert_id = await _add_certification(
            client, candidate, name="Phlebotomy Technician Certificate", skill_slug="phlebotomy"
        )

        headers = await _operator(client, db)
        refused = await client.post(
            f"/ops/candidates/certifications/{cert_id}/verify",
            headers=headers,
            json={"note": "ok"},
        )
        assert refused.status_code == 422

    async def test_a_second_certification_for_the_same_standard_upgrades_not_duplicates(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`_write_skills`'s own invariant: one row per skill per profile,
        regardless of which source added or upgraded it."""
        skill = await _skill(db, "phlebotomy")
        candidate = await _candidate(client)
        me = (await client.get("/auth/me", headers=candidate)).json()
        await client.post(
            "/me/profile/skills",
            headers=candidate,
            json={"skill_slug": "phlebotomy", "proficiency": 2},
        )
        cert_id = await _add_certification(
            client, candidate, name="Phlebotomy Technician Certificate", skill_slug="phlebotomy"
        )

        headers = await _operator(client, db)
        await client.post(
            f"/ops/candidates/certifications/{cert_id}/verify",
            headers=headers,
            json={"note": CERT_NOTE},
        )

        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == uuid.UUID(me["id"]))
        )
        assert profile is not None
        rows = list(
            await db.scalars(
                select(CandidateSkill).where(
                    CandidateSkill.profile_id == profile.id, CandidateSkill.skill_id == skill.id
                )
            )
        )
        assert len(rows) == 1
        assert rows[0].source == "certified"


# ----------------------------------------------- the organisation is told (BL-9.2)


class TestTheOrganisationIsTold:
    """Sprint 43. A decision changes what every candidate sees about an organisation
    and used to tell the organisation nothing. One email, only when the badge
    actually changes, naming the organisation and carrying no operator note."""

    async def _decide(self, client: AsyncClient, headers: dict, slug: str, decision: str) -> None:
        response = await client.post(
            f"/ops/organisations/{slug}/verification",
            headers=headers,
            json={"decision": decision, "note": f"{decision}: {NOTE}"},
        )
        assert response.status_code == 200, response.text

    async def _rows(self, db: AsyncSession) -> list[Notification]:
        db.expire_all()
        return list(
            await db.scalars(
                select(Notification)
                .where(Notification.template.like("organisation_verif%"))
                .order_by(Notification.created_at)
            )
        )

    async def test_granting_queues_one_email_to_the_organisation(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Told Ltd")
        operator = await _operator(client, db)

        await self._decide(client, operator, slug, "granted")

        (row,) = await self._rows(db)
        assert (row.template, row.channel, row.recipient_kind) == (
            "organisation_verified",
            "email",
            "tenant",
        )
        assert set(row.payload) == {"organisation", "path"}
        assert row.payload["organisation"] == "Told Ltd"
        assert row.payload["path"] == f"/employer/{slug}/settings"

    async def test_the_row_carries_no_address_and_no_operator_note(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Quiet Ltd")
        operator = await _operator(client, db)
        await self._decide(client, operator, slug, "granted")
        await self._decide(client, operator, slug, "revoked")

        rows = await self._rows(db)
        assert len(rows) == 2
        for row in rows:
            assert "@" not in str(row.payload)  # ADR-023: resolved at send time
            assert "Registration certificate" not in str(row.payload)  # evidence, not for email

    async def test_revoking_a_verified_organisation_queues_the_other_email(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Revoked Ltd")
        operator = await _operator(client, db)
        await self._decide(client, operator, slug, "granted")
        await self._decide(client, operator, slug, "revoked")

        assert [r.template for r in await self._rows(db)] == [
            "organisation_verified",
            "organisation_verification_revoked",
        ]

    async def test_a_regrant_of_a_verified_organisation_tells_nobody(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Re-verification is legitimate and the badge does not change, so there is
        nothing the organisation can see to be told about."""
        _, slug = await _register_org(client, "Again Ltd")
        operator = await _operator(client, db)
        await self._decide(client, operator, slug, "granted")
        await self._decide(client, operator, slug, "granted")

        assert [r.template for r in await self._rows(db)] == ["organisation_verified"]

    async def test_revoking_one_that_never_had_the_badge_tells_nobody(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        _, slug = await _register_org(client, "Never Ltd")
        operator = await _operator(client, db)
        await self._decide(client, operator, slug, "revoked")

        assert await self._rows(db) == []

    async def test_the_owner_receives_it_when_the_organisation_has_no_contact_address(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`Tenant.contact_email` is usually empty; the notice must reach the owner
        rather than be skipped, and must read as a notice about this organisation."""
        import api.modules.notifications.service as notifications

        owner, slug = await _register_org(client, "Reached Ltd")
        owner_email = (await client.get("/auth/me", headers=owner)).json()["email"]
        operator = await _operator(client, db)
        sent: list[tuple[str, str, str]] = []

        class Recording:
            async def send_email(self, address: str, subject: str, body: str) -> None:
                sent.append((address, subject, body))

        monkeypatch.setattr(notifications, "get_email_provider", lambda: Recording())
        await self._decide(client, operator, slug, "granted")
        counts = await drain(db)

        assert counts["sent"] == 1
        address, subject, body = sent[0]
        assert address == owner_email
        assert "Reached Ltd" in subject
        assert f"/employer/{slug}/settings" in body
        assert "Registration certificate" not in body

    async def test_an_owner_with_only_a_phone_is_skipped_not_failed(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Said plainly in the story rather than hidden: that organisation is not told."""
        headers = await _candidate(client)
        created = await client.post(
            "/me/organisations",
            headers=headers,
            json={"organisation_name": "Phone Only Ltd", "tenant_type": "employer"},
        )
        slug = created.json()["slug"]
        operator = await _operator(client, db)
        await self._decide(client, operator, slug, "granted")
        await drain(db)

        (row,) = await self._rows(db)
        assert row.status == "skipped" and row.last_error == "no address on file"

    async def test_the_notice_is_queued_before_the_decision_commits(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In the decision's own transaction: a notice that cannot be queued must not
        leave a changed badge nobody was told about, and a commit that came first
        could not be undone by a failed enqueue."""
        _, slug = await _register_org(client, "Ordered Ltd")
        operator = await _operator(client, db)
        order: list[str] = []
        real_enqueue, real_commit = service.enqueue, db.commit

        async def spy_enqueue(*args: object, **kwargs: object) -> object:
            order.append("enqueue")
            return await real_enqueue(*args, **kwargs)  # type: ignore[arg-type]

        async def spy_commit() -> None:
            order.append("commit")
            await real_commit()

        monkeypatch.setattr(service, "enqueue", spy_enqueue)
        monkeypatch.setattr(db, "commit", spy_commit)
        await self._decide(client, operator, slug, "granted")

        assert order[:2] == ["enqueue", "commit"]
