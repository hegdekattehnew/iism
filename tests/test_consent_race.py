"""Sprint 72: a withdrawal and an apply at the same moment must not leave contact shown.

An apply checks that the person has not withdrawn consent, then writes an application whose
contact an employer can read. A withdrawal stamps the person, then takes back what is live. Left
as a check followed by a write, an apply that passed its check just before the stamp commits
*after* the sweep has looked, and the employer holds the contact of somebody who withdrew consent.

`identity.consent` closes it with the user row: an apply reads the stamp under `FOR SHARE` and keeps
the lock until it commits, and the withdrawal's `UPDATE` of the stamp conflicts with it. Two
orderings, each made deterministic by holding the lock from a third session until the request is
provably waiting on it.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_sessionmaker
from api.modules.applications.models import Application
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile, Job
from tests.concurrency import (
    World,
    build_world,
    candidate,
    real_client,
    tear_down,
    wait_until_blocked,
)


@pytest.fixture
async def world() -> AsyncIterator[tuple[AsyncClient, World]]:
    async with real_client() as client:
        built = await build_world(client)
        try:
            yield client, built
        finally:
            await tear_down(client, built)


async def _user_id(client: AsyncClient, headers: dict[str, str]) -> uuid.UUID:
    return uuid.UUID((await client.get("/auth/me", headers=headers)).json()["id"])


@asynccontextmanager
async def _holding(user_id: uuid.UUID, *, share: bool) -> AsyncIterator[AsyncSession]:
    """A third session holding the user row, as the other request would mid-flight: `share` is an
    apply that has passed its check, otherwise a withdrawal whose `UPDATE` has not committed."""
    async with get_sessionmaker()() as session:
        await session.execute(
            select(User.id).where(User.id == user_id).with_for_update(read=share, of=User)
        )
        try:
            yield session
        finally:
            await session.rollback()


async def test_an_apply_in_flight_is_swept_up_by_the_withdrawal_that_waits_for_it(
    world: tuple[AsyncClient, World],
) -> None:
    """The apply got there first: the withdrawal waits for it, then takes its application back."""
    client, built = world
    headers = await candidate(client)
    built.candidates.append(headers)
    user_id = await _user_id(client, headers)

    async with get_sessionmaker()() as db:
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        job = await db.scalar(select(Job).where(Job.slug == built.job_slug))
        assert profile is not None and job is not None
        profile_id, job_id = profile.id, job.id

    async with _holding(user_id, share=True) as apply_in_flight:
        withdrawal = asyncio.create_task(
            client.post("/me/account/consent/withdraw", headers=headers)
        )
        await wait_until_blocked(1)  # the withdrawal is queued behind the apply
        apply_in_flight.add(
            Application(
                job_id=job_id,
                profile_id=profile_id,
                contact_shared_at=datetime.now(UTC),
            )
        )
        await apply_in_flight.commit()  # the apply lands, releasing its lock
    state = (await withdrawal).json()

    assert state["withdrawn"] is True and state["live_applications"] == 0
    async with get_sessionmaker()() as db:
        application = (
            await db.scalars(select(Application).where(Application.job_id == job_id))
        ).one()
        assert application.status == "withdrawn" and application.contact_revoked_at is not None


async def test_an_apply_that_waits_for_a_withdrawal_is_refused_after_it(
    world: tuple[AsyncClient, World],
) -> None:
    """The withdrawal got there first: the apply waits, re-reads the stamp, and is refused."""
    client, built = world
    headers = await candidate(client)
    built.candidates.append(headers)
    user_id = await _user_id(client, headers)

    async with _holding(user_id, share=False) as withdrawal_in_flight:
        apply = asyncio.create_task(
            client.post("/me/applications", headers=headers, json={"job_slug": built.job_slug})
        )
        await wait_until_blocked(1)  # the apply is queued behind the withdrawal
        user = await withdrawal_in_flight.get(User, user_id)
        assert user is not None
        user.consent_withdrawn_at = datetime.now(UTC)
        await withdrawal_in_flight.commit()
    response = await apply

    assert response.status_code == 409, response.text
    async with get_sessionmaker()() as db:
        assert (await db.scalars(select(Application))).all() == []
