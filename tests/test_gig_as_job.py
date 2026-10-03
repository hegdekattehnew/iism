"""Sprint 37, Epic B8: gig work reuses `Job`/`Application` (ADR-046,
superseding ADR-045). The owner's own framing -- "a temporary job assignment,
treated like a job" -- is what these tests hold to: a `gig` `Job` flows
through the existing matching pipeline with no change to `scoring.py` or
`matching/service.py`, and a gig engagement's outcome lives on `Application`,
the same place every other outcome already lives.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.applications.models import Application, ApplicationReview
from api.modules.geography.models import District, State
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, Job
from api.modules.marketplace.schemas import JobIn
from api.modules.skills.models import Skill


def _phone() -> str:
    return "9" + uuid.uuid4().int.__str__()[:9]


def _email() -> str:
    return f"gig-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"


async def _candidate(client: AsyncClient, phone: str | None = None) -> dict[str, str]:
    phone = phone or _phone()
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
    body = (
        await client.post(
            "/auth/email/otp/verify",
            json={"email": address, "code": code, "consent_version": CONSENT},
        )
    ).json()
    headers = {"authorization": f"Bearer {body['access_token']}"}
    slug = body["organisation_slug"]
    assert slug is not None
    return headers, slug


async def _skill(db: AsyncSession, slug: str) -> Skill:
    skill = Skill(slug=slug, name=slug.replace("-", " ").title(), skill_type="technical")
    db.add(skill)
    await db.flush()
    return skill


async def _geography(db: AsyncSession, *, state_name: str, district_name: str) -> None:
    state = State(
        state_code=abs(hash(state_name)) % 90000, slug=state_name.lower(), name=state_name
    )
    db.add(state)
    await db.flush()
    db.add(
        District(
            district_code=abs(hash(district_name)) % 90000, name=district_name, state_id=state.id
        )
    )
    await db.flush()


def _future(days: int = 3) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


class TestGigEmploymentType:
    async def test_a_gig_job_round_trips(self, db: AsyncSession) -> None:
        tenant = Tenant(
            name="Gig Co", slug=f"gig-co-{uuid.uuid4().hex[:8]}", tenant_type="employer"
        )
        db.add(tenant)
        await db.flush()
        job = Job(
            slug=f"gig-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant.id,
            title="Saturday warehouse shift",
            employment_type="gig",
            status="published",
            positions=3,
            closes_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.employment_type == "gig"

    async def test_an_unknown_employment_type_is_refused_by_the_database(
        self, db: AsyncSession
    ) -> None:
        tenant = Tenant(
            name="Bad Co", slug=f"bad-co-{uuid.uuid4().hex[:8]}", tenant_type="employer"
        )
        db.add(tenant)
        await db.flush()
        db.add(
            Job(
                slug=f"bad-{uuid.uuid4().hex[:8]}",
                tenant_id=tenant.id,
                title="Nonsense",
                employment_type="freelance",
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_a_candidate_can_prefer_gig_work(self, db: AsyncSession) -> None:
        user = User(phone=f"+9197{uuid.uuid4().int % 100000000:08d}")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id, preferred_employment_type="gig")
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        assert profile.preferred_employment_type == "gig"


class TestJobInValidation:
    def test_a_gig_with_no_closing_date_is_refused(self) -> None:
        with pytest.raises(ValueError, match="closes_at"):
            JobIn(title="No end in sight", employment_type="gig", closes_at=None, skills=[])

    def test_a_gig_with_a_future_closing_date_is_accepted(self) -> None:
        payload = JobIn(
            title="Saturday shift",
            employment_type="gig",
            closes_at=datetime.now(UTC) + timedelta(days=1),
            skills=[],
        )
        assert payload.employment_type == "gig"

    def test_a_permanent_job_still_needs_no_closing_date(self) -> None:
        JobIn(title="Ordinary vacancy", employment_type="full_time", skills=[])


class TestPostingAGig:
    async def test_positions_and_closes_at_actually_persist(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Regression test for the pre-existing bug this story depends on
        fixing: `_PLAIN_FIELDS` omitted both fields, so an employer's
        submission was silently dropped. Written to prove the fix, not just
        assume it."""
        await _geography(db, state_name="Gigstan", district_name="Shiftville")
        headers, slug = await _register_org(client, "Persist Co")
        closes = _future()
        created = (
            await client.post(
                f"/org/{slug}/jobs",
                headers=headers,
                json={
                    "title": "Weekend Loader",
                    "employment_type": "gig",
                    "location_state": "Gigstan",
                    "location_district": "Shiftville",
                    "positions": 3,
                    "closes_at": closes,
                    "skills": [],
                },
            )
        ).json()
        assert created["slug"]
        job = await db.scalar(select(Job).where(Job.slug == created["slug"]))
        assert job is not None
        assert job.positions == 3
        assert job.closes_at is not None

    async def test_a_gig_with_no_resolvable_district_is_refused(self, client: AsyncClient) -> None:
        headers, slug = await _register_org(client, "Nowhere Co")
        refused = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={
                "title": "Somewhere Shift",
                "employment_type": "gig",
                "location_state": "Nowhere State",
                "location_district": "Nowhere District",
                "closes_at": _future(),
                "skills": [],
            },
        )
        assert refused.status_code == 422

    async def test_a_gig_with_a_resolvable_district_is_accepted(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _geography(db, state_name="Realstan", district_name="Realtown")
        headers, slug = await _register_org(client, "Somewhere Co")
        created = await client.post(
            f"/org/{slug}/jobs",
            headers=headers,
            json={
                "title": "Real Shift",
                "employment_type": "gig",
                "location_state": "Realstan",
                "location_district": "Realtown",
                "closes_at": _future(),
                "skills": [],
            },
        )
        assert created.status_code == 201


async def _hire_via_gig(
    client: AsyncClient, db: AsyncSession, *, skill_slug: str
) -> tuple[dict[str, str], dict[str, str], str, str, str]:
    """A full gig lifecycle up to `hired`: employer, candidate, published gig
    job requiring `skill_slug`, an application, and a hire. Returns
    (employer_headers, candidate_headers, org_slug, job_slug, application_id).
    """
    state_name, district_name = f"State-{uuid.uuid4().hex[:6]}", f"District-{uuid.uuid4().hex[:6]}"
    await _geography(db, state_name=state_name, district_name=district_name)
    employer, org_slug = await _register_org(client, f"Hiring Co {uuid.uuid4().hex[:6]}")
    created = (
        await client.post(
            f"/org/{org_slug}/jobs",
            headers=employer,
            json={
                "title": "One-Day Gig",
                "employment_type": "gig",
                "location_state": state_name,
                "location_district": district_name,
                "closes_at": _future(),
                "positions": 1,
                "skills": [{"skill_slug": skill_slug, "importance": 3}],
            },
        )
    ).json()
    job_slug = created["slug"]
    await client.post(f"/org/{org_slug}/jobs/{job_slug}/publish", headers=employer)

    candidate = await _candidate(client)
    applied = (
        await client.post("/me/applications", headers=candidate, json={"job_slug": job_slug})
    ).json()
    application_id = applied["id"]

    await client.patch(
        f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
        headers=employer,
        json={"status": "hired"},
    )
    return employer, candidate, org_slug, job_slug, application_id


class TestApplicationOutcomeStateMachine:
    async def test_completed_from_applied_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _geography(db, state_name="OutcomeState", district_name="OutcomeDistrict")
        skill = await _skill(db, "outcome-skill-1")
        employer, org_slug = await _register_org(client, "Outcome Co")
        created = (
            await client.post(
                f"/org/{org_slug}/jobs",
                headers=employer,
                json={
                    "title": "Outcome Gig",
                    "employment_type": "gig",
                    "location_state": "OutcomeState",
                    "location_district": "OutcomeDistrict",
                    "closes_at": _future(),
                    "skills": [{"skill_slug": skill.slug, "importance": 3}],
                },
            )
        ).json()
        job_slug = created["slug"]
        await client.post(f"/org/{org_slug}/jobs/{job_slug}/publish", headers=employer)
        candidate = await _candidate(client)
        applied = (
            await client.post("/me/applications", headers=candidate, json={"job_slug": job_slug})
        ).json()

        refused = await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{applied['id']}",
            headers=employer,
            json={"status": "completed"},
        )
        assert refused.status_code == 409

    async def test_completed_on_a_permanent_job_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "permanent-skill-1")
        employer, org_slug = await _register_org(client, "Permanent Co")
        created = (
            await client.post(
                f"/org/{org_slug}/jobs",
                headers=employer,
                json={
                    "title": "Ordinary Role",
                    "skills": [{"skill_slug": skill.slug, "importance": 3}],
                },
            )
        ).json()
        job_slug = created["slug"]
        await client.post(f"/org/{org_slug}/jobs/{job_slug}/publish", headers=employer)
        candidate = await _candidate(client)
        applied = (
            await client.post("/me/applications", headers=candidate, json={"job_slug": job_slug})
        ).json()
        await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{applied['id']}",
            headers=employer,
            json={"status": "hired"},
        )

        refused = await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{applied['id']}",
            headers=employer,
            json={"status": "completed"},
        )
        assert refused.status_code == 422

    async def test_a_finished_engagement_cannot_be_moved_again(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`completed` and `no_show` record something that happened. Letting an
        employer move one back to `hired` or on to `rejected` rewrote it, and
        reopened a review window that closes for a reason."""
        skill = await _skill(db, "terminal-skill-1")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        url = f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}"
        assert (
            await client.patch(url, headers=employer, json={"status": "completed"})
        ).status_code == 200

        for target in ("hired", "rejected", "shortlisted", "no_show", "completed"):
            refused = await client.patch(url, headers=employer, json={"status": target})
            assert refused.status_code == 409, target

    async def test_a_no_show_is_final_too(self, client: AsyncClient, db: AsyncSession) -> None:
        skill = await _skill(db, "terminal-skill-2")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        url = f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}"
        await client.patch(url, headers=employer, json={"status": "no_show"})
        refused = await client.patch(url, headers=employer, json={"status": "hired"})
        assert refused.status_code == 409

    async def test_completed_on_a_gig_after_hired_succeeds(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "gig-hire-skill-1")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        done = await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
            headers=employer,
            json={"status": "completed"},
        )
        assert done.status_code == 200
        assert done.json()["status"] == "completed"


class TestReviews:
    async def test_reviewing_before_completed_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "review-early-skill")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        refused = await client.post(
            f"/me/applications/{application_id}/review",
            headers=candidate,
            json={"rating": 5, "comment": "Too soon"},
        )
        assert refused.status_code == 409

    async def test_both_directions_can_be_reviewed_after_completion(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "review-both-skill")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
            headers=employer,
            json={"status": "completed"},
        )

        worker_rates_poster = await client.post(
            f"/me/applications/{application_id}/review",
            headers=candidate,
            json={"rating": 5, "comment": "Paid on time"},
        )
        assert worker_rates_poster.status_code == 201
        assert worker_rates_poster.json()["subject_role"] == "poster"

        poster_rates_worker = await client.post(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}/review",
            headers=employer,
            json={"rating": 4, "comment": "Showed up on time"},
        )
        assert poster_rates_worker.status_code == 201
        assert poster_rates_worker.json()["subject_role"] == "worker"

    async def test_a_second_review_in_the_same_direction_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "review-dup-skill")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
            headers=employer,
            json={"status": "completed"},
        )
        await client.post(
            f"/me/applications/{application_id}/review",
            headers=candidate,
            json={"rating": 5},
        )
        duplicate = await client.post(
            f"/me/applications/{application_id}/review",
            headers=candidate,
            json={"rating": 1},
        )
        assert duplicate.status_code == 409

    async def test_a_no_show_engagement_cannot_be_reviewed(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "review-noshow-skill")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
            headers=employer,
            json={"status": "no_show"},
        )
        refused = await client.post(
            f"/me/applications/{application_id}/review",
            headers=candidate,
            json={"rating": 1},
        )
        assert refused.status_code == 409

    async def test_a_stranger_cannot_review_someone_elses_application(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "review-stranger-skill")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
            headers=employer,
            json={"status": "completed"},
        )
        stranger = await _candidate(client)
        refused = await client.post(
            f"/me/applications/{application_id}/review",
            headers=stranger,
            json={"rating": 5},
        )
        assert refused.status_code == 404


class TestApplicationReviewModel:
    async def test_both_directions_round_trip_for_one_application(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "model-review-skill")
        _, _, _, _, application_id = await _hire_via_gig(client, db, skill_slug=skill.slug)
        application = await db.get(Application, uuid.UUID(application_id))
        assert application is not None
        db.add(ApplicationReview(application_id=application.id, subject_role="poster", rating=5))
        db.add(ApplicationReview(application_id=application.id, subject_role="worker", rating=4))
        await db.commit()

    async def test_a_duplicate_direction_is_refused_by_the_database(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "model-review-dup-skill")
        _, _, _, _, application_id = await _hire_via_gig(client, db, skill_slug=skill.slug)
        application_uuid = uuid.UUID(application_id)
        db.add(ApplicationReview(application_id=application_uuid, subject_role="poster", rating=5))
        await db.commit()
        db.add(ApplicationReview(application_id=application_uuid, subject_role="poster", rating=1))
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_an_out_of_range_rating_is_refused_by_the_database(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "model-review-range-skill")
        _, _, _, _, application_id = await _hire_via_gig(client, db, skill_slug=skill.slug)
        db.add(
            ApplicationReview(
                application_id=uuid.UUID(application_id), subject_role="poster", rating=6
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()


class TestGigAppearsInMatching:
    async def test_a_gig_ranks_in_a_matching_candidates_results(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The concrete proof reuse works: zero changes to `matching/service.py`
        or `scoring.py` are needed for a gig to appear, scored, in a
        candidate's ranked matches."""
        await _geography(db, state_name="MatchState", district_name="MatchDistrict")
        skill = Skill(
            slug="match-gig-skill",
            name="Handle warehouse inventory",
            skill_type="technical",
            nsqf_level=Decimal("3"),
            nos_code="TST/GIG001",
            source="nsqf",
        )
        db.add(skill)
        await db.flush()

        employer, org_slug = await _register_org(client, "Matching Gig Co")
        created = (
            await client.post(
                f"/org/{org_slug}/jobs",
                headers=employer,
                json={
                    "title": "Inventory Shift",
                    "employment_type": "gig",
                    "location_state": "MatchState",
                    "location_district": "MatchDistrict",
                    "closes_at": _future(),
                    "skills": [{"skill_slug": skill.slug, "importance": 5, "is_mandatory": True}],
                },
            )
        ).json()
        job_slug = created["slug"]
        await client.post(f"/org/{org_slug}/jobs/{job_slug}/publish", headers=employer)

        candidate = await _candidate(client)
        await client.post(
            "/me/profile/skills",
            headers=candidate,
            json={"skill_slug": skill.slug, "proficiency": 4},
        )

        matches = (await client.get("/me/matches", headers=candidate)).json()
        slugs = [item["job"]["slug"] for item in matches["items"]]
        assert job_slug in slugs


async def _gig_with_outcomes(db: AsyncSession, statuses: list[str], *, positions: int) -> Job:
    tenant = Tenant(slug=f"fill-{uuid.uuid4().hex[:8]}", name="Fill Co", tenant_type="employer")
    db.add(tenant)
    await db.flush()
    job = Job(
        slug=f"fill-gig-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant.id,
        title="Shift",
        status="published",
        employment_type="gig",
        positions=positions,
        closes_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add(job)
    await db.flush()
    for status in statuses:
        user = User(phone=f"+9194{uuid.uuid4().int % 100000000:08d}")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
        db.add(Application(job_id=job.id, profile_id=profile.id, status=status))
    await db.flush()
    return job


class TestAFinishedGigStillFillsItsPosition:
    """`completed` moves a worker out of `hired`. Counting `hired` alone let a
    two-position gig take on a third person once the first had finished."""

    async def test_a_completed_worker_still_occupies_a_position(self, db: AsyncSession) -> None:
        from api.modules.applications.employer_service import _close_if_filled

        job = await _gig_with_outcomes(db, ["completed", "hired"], positions=2)
        assert await _close_if_filled(db, job) is True
        assert job.close_reason == "filled"

    async def test_a_no_show_leaves_the_position_open(self, db: AsyncSession) -> None:
        from api.modules.applications.employer_service import _close_if_filled

        job = await _gig_with_outcomes(db, ["no_show", "hired"], positions=2)
        assert await _close_if_filled(db, job) is False
        assert job.closed_at is None


class TestDashboardsKeepCountingAFinishedGig:
    """Both dashboards summed `status == "hired"`, so a gig worker dropped out
    of the figure the moment the gig was marked completed."""

    async def test_the_candidates_hired_count_survives_completion(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "dash-completed-skill")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        assert (await client.get("/me/dashboard", headers=candidate)).json()["hired"] == 1

        await client.patch(
            f"/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
            headers=employer,
            json={"status": "completed"},
        )
        assert (await client.get("/me/dashboard", headers=candidate)).json()["hired"] == 1

    async def test_the_employers_hired_count_survives_completion_and_no_show(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        from api.modules.applications.employer_service import dashboard

        job = await _gig_with_outcomes(
            db, ["completed", "no_show", "hired", "rejected"], positions=9
        )
        result = await dashboard(db, job.tenant_id)
        assert result.hired == 3


class TestDashboardMatchCount:
    async def test_match_count_is_not_cut_at_twenty(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`match_count` was `len()` of a list `match_jobs` had already cut to
        its default page of twenty, so it could never say more than twenty."""
        from api.modules.marketplace.models import JobSkill

        skill = Skill(
            slug="count-skill",
            name="Operate a till",
            skill_type="technical",
            nsqf_level=Decimal("3"),
            nos_code="TST/CNT001",
            source="nsqf",
        )
        db.add(skill)
        tenant = Tenant(
            slug=f"count-{uuid.uuid4().hex[:8]}", name="Count Co", tenant_type="employer"
        )
        db.add(tenant)
        await db.flush()
        for i in range(25):
            job = Job(
                slug=f"count-job-{uuid.uuid4().hex[:8]}-{i}",
                tenant_id=tenant.id,
                title=f"Cashier {i}",
                status="published",
            )
            db.add(job)
            await db.flush()
            db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=3, is_mandatory=True))
        await db.flush()

        candidate = await _candidate(client)
        await client.post(
            "/me/profile/skills",
            headers=candidate,
            json={"skill_slug": skill.slug, "proficiency": 4},
        )

        dashboard = (await client.get("/me/dashboard", headers=candidate)).json()
        assert dashboard["match_count"] == 25
        assert len(dashboard["top_matches"]) == 5


async def _rate(
    db: AsyncSession, application: Application, *, about: str, rating: int
) -> ApplicationReview:
    review = ApplicationReview(application_id=application.id, subject_role=about, rating=rating)
    db.add(review)
    await db.flush()
    return review


async def _applications_of(db: AsyncSession, job: Job) -> list[Application]:
    return list(await db.scalars(select(Application).where(Application.job_id == job.id)))


class TestReviewedFlags:
    """The rating form could not tell whether to show itself, because nothing
    said a review already existed and the API answers a second one with 409."""

    async def test_each_side_sees_only_its_own_review(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "flag-skill-1")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        url = f"/org/{org_slug}/jobs/{job_slug}/applications"
        await client.patch(
            f"{url}/{application_id}", headers=employer, json={"status": "completed"}
        )

        def employer_flag() -> object:
            return client.get(url, headers=employer)

        before = (await employer_flag()).json()["items"][0]["reviewed"]
        mine_before = (await client.get("/me/applications", headers=candidate)).json()[0][
            "reviewed"
        ]
        assert before is False and mine_before is False

        await client.post(f"{url}/{application_id}/review", headers=employer, json={"rating": 4})
        # The employer has rated the worker; the worker has not yet rated them.
        assert (await employer_flag()).json()["items"][0]["reviewed"] is True
        assert (await client.get("/me/applications", headers=candidate)).json()[0][
            "reviewed"
        ] is False

        await client.post(
            f"/me/applications/{application_id}/review", headers=candidate, json={"rating": 5}
        )
        assert (await client.get("/me/applications", headers=candidate)).json()[0][
            "reviewed"
        ] is True


class TestReputation:
    async def test_an_average_over_nothing_is_absent_not_zero(self, db: AsyncSession) -> None:
        from api.modules.applications.reputation import poster_reputation, worker_reputation

        job = await _gig_with_outcomes(db, ["completed"], positions=1)
        application = (await _applications_of(db, job))[0]
        assert await poster_reputation(db, job.tenant_id) is None
        assert await worker_reputation(db, application.profile_id) is None

    async def test_a_poster_is_rated_by_workers_across_all_their_vacancies(
        self, db: AsyncSession
    ) -> None:
        from api.modules.applications.reputation import poster_reputation

        job = await _gig_with_outcomes(db, ["completed", "completed", "completed"], positions=3)
        apps = await _applications_of(db, job)
        await _rate(db, apps[0], about="poster", rating=5)
        await _rate(db, apps[1], about="poster", rating=4)
        # Rated *about the worker*: must not count towards the poster.
        await _rate(db, apps[2], about="worker", rating=1)

        result = await poster_reputation(db, job.tenant_id)
        assert result is not None
        assert (result.average, result.count) == (4.5, 2)

    async def test_a_workers_rating_is_what_employers_said_about_them(
        self, db: AsyncSession
    ) -> None:
        from api.modules.applications.reputation import worker_reputation

        job = await _gig_with_outcomes(db, ["completed"], positions=1)
        application = (await _applications_of(db, job))[0]
        await _rate(db, application, about="worker", rating=3)
        await _rate(db, application, about="poster", rating=5)

        result = await worker_reputation(db, application.profile_id)
        assert result is not None
        assert (result.average, result.count) == (3.0, 1)

    async def test_the_public_poster_rating_for_a_vacancy(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job = await _gig_with_outcomes(db, ["completed", "completed"], positions=2)
        apps = await _applications_of(db, job)
        empty = await client.get(f"/jobs/{job.slug}/poster-rating")
        assert empty.status_code == 200
        assert empty.json() == {"rating": None}

        await _rate(db, apps[0], about="poster", rating=5)
        await _rate(db, apps[1], about="poster", rating=3)
        await db.commit()
        rated = await client.get(f"/jobs/{job.slug}/poster-rating")
        assert rated.json() == {"rating": {"average": 4.0, "count": 2}}

    async def test_a_draft_or_unknown_vacancy_gives_nothing_away(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job = await _gig_with_outcomes(db, ["completed"], positions=1)
        job.status = "draft"
        await _rate(db, (await _applications_of(db, job))[0], about="poster", rating=5)
        await db.commit()

        assert (await client.get(f"/jobs/{job.slug}/poster-rating")).json() == {"rating": None}
        assert (await client.get("/jobs/no-such-job/poster-rating")).json() == {"rating": None}

    async def test_the_dashboards_carry_the_rating_and_the_card_never_does(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await _skill(db, "rating-dash-skill")
        employer, candidate, org_slug, job_slug, application_id = await _hire_via_gig(
            client, db, skill_slug=skill.slug
        )
        url = f"/org/{org_slug}/jobs/{job_slug}/applications"
        await client.patch(
            f"{url}/{application_id}", headers=employer, json={"status": "completed"}
        )
        await client.post(f"{url}/{application_id}/review", headers=employer, json={"rating": 2})
        await client.post(
            f"/me/applications/{application_id}/review", headers=candidate, json={"rating": 5}
        )

        employer_dash = (await client.get(f"/org/{org_slug}/dashboard", headers=employer)).json()
        assert employer_dash["rating"] == {"average": 5.0, "count": 1}
        candidate_dash = (await client.get("/me/dashboard", headers=candidate)).json()
        assert candidate_dash["rating"] == {"average": 2.0, "count": 1}

        # ADR-037: a rating is a fact about one person, and the employer's view
        # of a candidate is de-identified.
        listing = (await client.get(url, headers=employer)).json()["items"][0]
        assert "rating" not in listing["candidate"]
        assert "rating" not in listing
