"""Withdrawing consent without deleting the account (Sprint 72, ADR-082).

The notice used to say withdrawing *was* deleting. Now a person can pause their account and every
claim a pause makes has to be true: they are not offered to an employer or alerted, they cannot
apply or register interest, the disclosures that exist are taken back, nothing is tracked or
pushed, and they can come back by confirming the notice in force. Each rule is read at one choke
point, so each has a test that fails when that point stops reading it.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.applications import Application
from api.modules.identity import Tenant, User
from api.modules.interests import CourseInterest
from api.modules.marketplace.models import (
    CandidateProfile,
    CandidateSkill,
    Course,
    CourseSkill,
    Job,
    JobSkill,
)
from api.modules.matching.retrieval import pool_counts
from api.modules.notifications import Notification
from api.modules.notifications import service as notifications_service
from api.modules.notifications.service import _sweep_push
from api.modules.skills import Skill
from tests.test_operations import _candidate
from tests.test_push_sweep import PAYLOAD, Recorder, _give_phone, _tell


@pytest.fixture
async def world(db: AsyncSession) -> dict:
    """One vacancy and one course that want the same standard."""
    skill = Skill(
        slug="consent-standard",
        name="Handle consent",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N7201",
        source="nsqf",
    )
    employer = Tenant(slug="consent-co", name="Consent Co", tenant_type="employer")
    provider = Tenant(slug="consent-school", name="Consent School", tenant_type="course_provider")
    db.add_all([skill, employer, provider])
    await db.flush()
    job = Job(
        slug="consent-job",
        tenant_id=employer.id,
        title="Consent clerk",
        employment_type="full_time",
        status="published",
    )
    course = Course(slug="consent-course", tenant_id=provider.id, title="Consent 101")
    course.status = "published"
    db.add_all([job, course])
    await db.flush()
    db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=5, is_mandatory=True))
    db.add(CourseSkill(course_id=course.id, skill_id=skill.id, level_taught=Decimal("4")))
    await db.commit()
    return {
        "job_id": job.id,
        "job_slug": job.slug,
        "course_slug": course.slug,
        "skill_id": skill.id,
    }


async def _person(client: AsyncClient, db: AsyncSession, world: dict) -> tuple[dict, uuid.UUID]:
    """A signed-in candidate who holds the standard, and their user id."""
    headers = await _candidate(client)
    user_id = uuid.UUID((await client.get("/auth/me", headers=headers)).json()["id"])
    await client.get("/me/profile", headers=headers)  # the lazy profile
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    assert profile is not None
    db.add(
        CandidateSkill(profile_id=profile.id, skill_id=world["skill_id"], source="self_declared")
    )
    await db.commit()
    return headers, user_id


async def _pool(db: AsyncSession, world: dict) -> int:
    return (await pool_counts(db, [world["job_id"]]))[world["job_id"]][0]


async def test_a_withdrawal_is_a_pause_not_a_deletion(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, user_id = await _person(client, db, world)
    state = (await client.post("/me/account/consent/withdraw", headers=headers)).json()
    assert state["withdrawn"] is True and state["consent_withdrawn_at"] is not None
    # Still there: the account, the profile, and the way back.
    assert await db.get(User, user_id) is not None
    assert (await client.get("/me/profile", headers=headers)).status_code == 200
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["consent_withdrawn"] is True


async def test_a_paused_person_is_not_offered_to_an_employer(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, _ = await _person(client, db, world)
    assert await _pool(db, world) == 1
    await client.post("/me/account/consent/withdraw", headers=headers)
    db.expire_all()
    assert await _pool(db, world) == 0
    version = (await client.get("/me/account/consent", headers=headers)).json()["notice_version"]
    await client.post("/me/account/consent", json={"consent_version": version}, headers=headers)
    db.expire_all()
    assert await _pool(db, world) == 1


async def test_a_paused_person_cannot_apply_or_register_interest(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, _ = await _person(client, db, world)
    await client.post("/me/account/consent/withdraw", headers=headers)
    applied = await client.post(
        "/me/applications", json={"job_slug": world["job_slug"]}, headers=headers
    )
    assert applied.status_code == 409 and "withdrawn consent" in applied.json()["detail"]
    interested = await client.post(
        "/me/course-interests", json={"course_slug": world["course_slug"]}, headers=headers
    )
    assert interested.status_code == 409
    assert await db.scalar(select(func.count()).select_from(Application)) == 0
    assert await db.scalar(select(func.count()).select_from(CourseInterest)) == 0


async def test_withdrawing_takes_back_contact_already_shared(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, _ = await _person(client, db, world)
    assert (
        await client.post("/me/applications", json={"job_slug": world["job_slug"]}, headers=headers)
    ).status_code == 201
    assert (
        await client.post(
            "/me/course-interests", json={"course_slug": world["course_slug"]}, headers=headers
        )
    ).status_code == 201

    before = (await client.get("/me/account/consent", headers=headers)).json()
    assert (before["live_applications"], before["live_interests"]) == (1, 1)
    assert before["withdrawn"] is False  # the preview changes nothing

    after = (await client.post("/me/account/consent/withdraw", headers=headers)).json()
    assert (after["live_applications"], after["live_interests"]) == (0, 0)
    db.expire_all()
    application = (await db.scalars(select(Application))).one()
    interest = (await db.scalars(select(CourseInterest))).one()
    assert application.status == "withdrawn" and application.contact_revoked_at is not None
    assert interest.status == "withdrawn" and interest.contact_revoked_at is not None


async def test_an_employers_decision_is_kept_when_a_candidate_withdraws_consent(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    """A rejection is the employer's record (ADR-052); the sweep skips it rather than failing."""
    headers, _ = await _person(client, db, world)
    await client.post("/me/applications", json={"job_slug": world["job_slug"]}, headers=headers)
    application = (await db.scalars(select(Application))).one()
    application.status = "rejected"
    await db.commit()
    state = (await client.post("/me/account/consent/withdraw", headers=headers)).json()
    assert state["withdrawn"] is True
    db.expire_all()
    assert (await db.scalars(select(Application))).one().status == "rejected"


async def test_withdrawing_twice_is_the_same_as_once(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, user_id = await _person(client, db, world)
    first = (await client.post("/me/account/consent/withdraw", headers=headers)).json()
    second = (await client.post("/me/account/consent/withdraw", headers=headers)).json()
    assert first["consent_withdrawn_at"] == second["consent_withdrawn_at"]


async def test_restoring_needs_the_notice_in_force_and_clears_the_stamp(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, _ = await _person(client, db, world)
    await client.post("/me/account/consent/withdraw", headers=headers)
    stale = await client.post(
        "/me/account/consent", json={"consent_version": "1999-01-01"}, headers=headers
    )
    assert stale.status_code == 422 and stale.json()["detail"] == "consent_required"
    assert (await client.get("/auth/me", headers=headers)).json()["consent_withdrawn"] is True

    ok = await client.post(
        "/me/account/consent", json={"consent_version": CONSENT}, headers=headers
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["withdrawn"] is False and body["current"] is True
    applied = await client.post(
        "/me/applications", json={"job_slug": world["job_slug"]}, headers=headers
    )
    assert applied.status_code == 201


async def test_a_stale_notice_prompts_and_never_blocks(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, user_id = await _person(client, db, world)
    user = await db.get(User, user_id)
    assert user is not None
    user.consent_version = "2020-01-01"
    await db.commit()
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["consent_current"] is False and me["consent_withdrawn"] is False
    # Not blocked: the person can still do everything while the banner asks.
    assert (
        await client.post("/me/applications", json={"job_slug": world["job_slug"]}, headers=headers)
    ).status_code == 201
    await client.post("/me/account/consent", json={"consent_version": CONSENT}, headers=headers)
    assert (await client.get("/auth/me", headers=headers)).json()["consent_current"] is True


async def test_a_paused_person_is_not_tracked(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, user_id = await _person(client, db, world)

    async def events() -> int:
        return (
            await db.scalar(
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(AnalyticsEvent.user_id == user_id)
            )
        ) or 0

    await client.get("/me/matches", headers=headers)
    tracked = await events()
    assert tracked >= 1  # found what it is counting before judging the paused case
    await client.post("/me/account/consent/withdraw", headers=headers)
    await client.get("/me/matches", headers=headers)
    await client.get("/me/matches", headers=headers)
    assert await events() == tracked


async def test_a_paused_person_is_not_pushed_to(
    client: AsyncClient, db: AsyncSession, world: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(notifications_service, "get_push_provider", lambda: recorder)
    _, paused_id = await _person(client, db, world)
    _, active_id = await _person(client, db, world)
    for uid in (paused_id, active_id):
        await _give_phone(db, uid)
        await _tell(db, uid, payload=PAYLOAD)
    paused = await db.get(User, paused_id)
    assert paused is not None
    paused.consent_withdrawn_at = paused.created_at
    await db.commit()

    counts = await _sweep_push(db, limit=50)
    assert counts["sent"] == 1  # the person who did not withdraw
    notices = (await db.scalars(select(Notification))).all()
    assert all(n.pushed_at is not None for n in notices)  # stamped, so not owed for ever
    assert len(recorder.sent) == 1


async def test_the_export_says_when_consent_was_withdrawn(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    headers, _ = await _person(client, db, world)
    await client.post("/me/account/consent/withdraw", headers=headers)
    export = (await client.get("/me/account/export", headers=headers)).json()
    assert export["account"]["consent_withdrawn_at"] is not None


async def test_an_organisation_only_account_can_withdraw_and_gets_no_profile(
    client: AsyncClient, db: AsyncSession
) -> None:
    from tests.test_applications import _organisation

    headers = await _organisation(client)
    state = (await client.post("/me/account/consent/withdraw", headers=headers)).json()
    assert state["withdrawn"] is True
    assert (state["live_applications"], state["live_interests"]) == (0, 0)
    assert await db.scalar(select(func.count()).select_from(CandidateProfile)) == 0


async def test_a_paused_person_is_not_a_job_seeker_in_the_public_figure(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    """`skilled_profile()` is the one definition of "job seeker" (ADR-061): a paused person is not
    offered to anyone, so neither the homepage nor the employer console counts them."""
    from api.modules.marketplace.models import skilled_profile

    headers, _ = await _person(client, db, world)

    async def seekers() -> int:
        return (
            await db.scalar(
                select(func.count()).select_from(CandidateProfile).where(skilled_profile())
            )
        ) or 0

    before = await seekers()
    assert before >= 1
    await client.post("/me/account/consent/withdraw", headers=headers)
    db.expire_all()
    assert await seekers() == before - 1


async def test_a_batch_of_events_skips_the_paused_person_and_keeps_the_rest(
    client: AsyncClient, db: AsyncSession, world: dict
) -> None:
    from api.modules.analytics import record_many

    _, paused_id = await _person(client, db, world)
    _, active_id = await _person(client, db, world)
    paused = await db.get(User, paused_id)
    assert paused is not None
    paused.consent_withdrawn_at = paused.created_at
    await db.commit()

    await record_many(
        db,
        [
            ("matches_viewed", {"user_id": paused_id}),
            ("matches_viewed", {"user_id": active_id}),
        ],
    )
    stored = (
        await db.scalars(
            select(AnalyticsEvent.user_id).where(AnalyticsEvent.user_id.in_([paused_id, active_id]))
        )
    ).all()
    assert active_id in stored and paused_id not in stored
