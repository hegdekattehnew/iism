"""Shared set-up for tests that need two requests genuinely at once.

The suite's `db` fixture wraps one connection in one transaction that is always
rolled back, which is exactly right for almost every test and exactly wrong for a
race: two requests sharing one connection take turns, and neither can ever block
the other. A race test therefore needs **committed** rows, requests that each get
their own session from the real sessionmaker, and a way to clean up afterwards.

Two techniques, both deterministic where a bare `asyncio.gather` is not:

* **Hold a row lock, release it when both requests are waiting.** Without a fix,
  both requests pass their status check and queue at the `UPDATE`; with one, both
  queue at the `SELECT ... FOR UPDATE`. Either way they are provably in flight
  together (`pg_stat_activity` says so) before either is allowed to finish.
* **Widen the window after a check** by wrapping the function that follows it, for
  the cases where the interleaving point is not a row the test can lock.

Sprint 44 used the second for the ownership race; Sprint 45 added the first.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.database import get_sessionmaker
from api.main import app
from api.modules.marketplace.models import Course, CourseSkill, Job, JobSkill
from api.modules.skills import Skill


@asynccontextmanager
async def real_client() -> AsyncIterator[AsyncClient]:
    """A client whose requests each open their own session, as in production."""
    assert not app.dependency_overrides, "a race test must not share the rolled-back session"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def candidate(client: AsyncClient) -> dict[str, str]:
    """A signed-in candidate **with a profile already created**.

    `ensure_profile` is lazy, so a brand-new candidate's first two requests race to
    create it -- a different race from the one under test, and one that hides it.
    """
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    headers = {"authorization": f"Bearer {body['access_token']}"}
    await client.get("/me/applications", headers=headers)  # creates the profile
    return headers


async def organisation(
    client: AsyncClient, tenant_type: str, name: str
) -> tuple[dict[str, str], str]:
    address = f"race-{uuid.uuid4().hex[:10]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": name,
                "tenant_type": tenant_type,
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    return {"authorization": f"Bearer {tokens['access_token']}"}, tokens["organisation_slug"]


@dataclass
class World:
    """One employer with a published vacancy and one provider with a published course."""

    employer: dict[str, str]
    employer_slug: str
    employer_name: str
    provider: dict[str, str]
    provider_slug: str
    provider_name: str
    job_slug: str
    course_slug: str
    skill_id: uuid.UUID
    candidates: list[dict[str, str]] = field(default_factory=list)


async def build_world(client: AsyncClient) -> World:
    tag = uuid.uuid4().hex[:8]
    employer_name, provider_name = f"Race Employer {tag}", f"Race Provider {tag}"
    employer, employer_slug = await organisation(client, "employer", employer_name)
    provider, provider_slug = await organisation(client, "course_provider", provider_name)
    async with get_sessionmaker()() as db:
        from api.modules.identity import Tenant

        skill = Skill(
            slug=f"race-std-{tag}",
            name="Race standard",
            skill_type="technical",
            nsqf_level=Decimal("4"),
            nos_code=f"TST/N{int(tag, 16) % 9000 + 1000}",
            source="nsqf",
        )
        employer_row = await db.scalar(select(Tenant).where(Tenant.slug == employer_slug))
        provider_row = await db.scalar(select(Tenant).where(Tenant.slug == provider_slug))
        assert employer_row is not None and provider_row is not None
        db.add(skill)
        await db.flush()
        job = Job(
            slug=f"race-job-{tag}",
            tenant_id=employer_row.id,
            title="Race vacancy",
            employment_type="full_time",
            status="published",
            positions=50,
        )
        course = Course(
            slug=f"race-course-{tag}",
            tenant_id=provider_row.id,
            title="Race course",
            status="published",
        )
        db.add_all([job, course])
        await db.flush()
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=5, is_mandatory=True))
        db.add(CourseSkill(course_id=course.id, skill_id=skill.id))
        await db.commit()
        return World(
            employer=employer,
            employer_slug=employer_slug,
            employer_name=employer_name,
            provider=provider,
            provider_slug=provider_slug,
            provider_name=provider_name,
            job_slug=job.slug,
            course_slug=course.slug,
            skill_id=skill.id,
        )


async def tear_down(client: AsyncClient, world: World) -> None:
    """Through the app's own erasure routes, so what is left is what a user could leave."""
    for headers in world.candidates:
        await client.delete("/me/account", headers=headers)
    await client.delete(
        f"/org/{world.employer_slug}",
        headers=world.employer,
        params={"confirm": world.employer_name},
    )
    await client.delete(
        f"/org/{world.provider_slug}",
        headers=world.provider,
        params={"confirm": world.provider_name},
    )
    async with get_sessionmaker()() as db:
        await db.execute(delete(Skill).where(Skill.id == world.skill_id))
        await db.commit()


@asynccontextmanager
async def row_locked(model: Any, row_id: uuid.UUID) -> AsyncIterator[None]:
    """Hold `FOR UPDATE` on one row from a third session until the block exits."""
    async with get_sessionmaker()() as session:
        await session.execute(select(model.id).where(model.id == row_id).with_for_update())
        try:
            yield
        finally:
            await session.rollback()


async def wait_until_blocked(count: int, *, wait_seconds: float = 8.0) -> None:
    """Return once `count` backends are waiting on a lock -- proof they are in flight together.

    Fails loudly rather than hanging: if the requests never block, the test has
    not set up the race it claims to, and a green result would be meaningless.
    """
    deadline = asyncio.get_running_loop().time() + wait_seconds
    while True:
        async with get_sessionmaker()() as session:
            waiting = await session.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND datname = current_database()"
                )
            )
        if (waiting or 0) >= count:
            return
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"expected {count} requests waiting on a lock, saw {waiting}")
        await asyncio.sleep(0.05)
