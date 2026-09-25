"""The back office, and the authority that reaches it (ADR-042).

`tenants.is_verified` existed for sixteen sprints with no writer: a column, a
read on the public payload, a read in the interface, and a test asserting it
could not be written. This is the sprint it gained one, and the tests below are
mostly about what that writer must *refuse*.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import (
    OPERATOR_PERMISSIONS,
    ROLE_PERMISSIONS,
    Permission,
    require_operator,
)
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.applications.models import Application
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import (
    CandidateProfile,
    CandidateSkill,
    Job,
    JobSkill,
)
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


async def _operator(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    """An account holding the flag. Granted the way the product grants it."""
    headers = await _candidate(client)
    me = (await client.get("/auth/me", headers=headers)).json()
    user = await db.get(User, uuid.UUID(me["id"]))
    assert user is not None
    user.is_staff = True
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
        rename cannot make this pass by finding nothing anywhere.
        """
        schema = (await client.get("/openapi.json")).json()
        components = schema["components"]["schemas"]
        assert "is_staff" in components["UserOut"]["properties"]

        for name, model in components.items():
            if name.endswith(("In", "Request", "Verify", "Update")):
                assert "is_staff" not in model.get("properties", {}), name


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
            await service.set_staff(db, address=address, staff=True)
        assert await db.scalar(select(User).where(User.email == address)) is None

    async def test_it_grants_and_revokes_an_account_that_exists(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, _ = await _register_org(client, "Roster Ltd")
        me = (await client.get("/auth/me", headers=headers)).json()
        assert me["is_staff"] is False

        await service.set_staff(db, address=me["email"], staff=True)
        assert (await client.get("/auth/me", headers=headers)).json()["is_staff"] is True

        await service.set_staff(db, address=me["email"], staff=False)
        assert (await client.get("/auth/me", headers=headers)).json()["is_staff"] is False

    async def test_the_roster_answers_who_else_holds_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _operator(client, db)
        assert len(await service.staff_roster(db)) >= 1


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
