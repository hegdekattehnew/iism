"""What a bulk apply does when a row is refused or loses a race (Sprint 55, from the review).

These need **committed** rows and a session of their own per request (`tests/concurrency.py`): the
suite's `db` fixture wraps one connection in a transaction it never commits, so a `rollback()` in
the code under test would roll back the test's own set-up, and the thing being pinned (what a
rollback does to the rest of the loop) could not be seen.

Two defects, found by reading the apply loop:

* A writer that refuses *after* it has started changing a listing leaves that listing dirty in the
  session, and the next commit in the loop saves the edit the person was just told was rejected.
* `db.rollback()` expires every instance in the session, including the `Tenant`, and the loop read
  `tenant.id` after it: a synchronous load inside the event loop, so a race on one row was a 500 for
  the whole file.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.core.database import get_sessionmaker
from api.modules.marketplace import publishing
from api.modules.marketplace.models import Job
from tests.concurrency import World, build_world, real_client, tear_down

UPDATE = "?existing=update"


@pytest.fixture
async def world() -> AsyncIterator[tuple[AsyncClient, World]]:
    async with real_client() as client:
        built = await build_world(client)
        try:
            yield client, built
        finally:
            await tear_down(client, built)


async def _upload(client: AsyncClient, world: World, text: str, *, query: str = "") -> dict:
    response = await client.post(
        f"/org/{world.employer_slug}/jobs/bulk/apply{query}",
        content=text.encode(),
        headers={**world.employer, "content-type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _title(slug: str) -> str:
    async with get_sessionmaker()() as db:
        return str(await db.scalar(select(Job.title).where(Job.slug == slug)))


class TestARefusedRowIsNotSavedByTheNextOne:
    async def test_a_listing_a_writer_half_changed_and_then_refused_keeps_its_old_values(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, w = world
        made = await _upload(client, w, "external_ref,title\nR1,Alpha\nR2,Beta\n")
        first, second = (r["slug"] for r in made["rows"])

        original = publishing.update_job

        async def refuses_after_touching_the_row(db, tenant_id, slug, payload):  # type: ignore[no-untyped-def]
            if slug == first:
                job = await db.scalar(select(Job).where(Job.slug == slug))
                job.title = "HALF-APPLIED"  # what a writer that fails late has already done
                raise HTTPException(422, "refused after it had started")
            return await original(db, tenant_id, slug, payload)

        monkeypatch.setattr(publishing, "update_job", refuses_after_touching_the_row)

        body = await _upload(
            client, w, "external_ref,title\nR1,Alpha two\nR2,Beta two\n", query=UPDATE
        )

        assert [r["status"] for r in body["rows"]] == ["error", "update"]
        assert body["updated"] == 1
        assert await _title(second) == "Beta two"
        # The point: row 2's commit must not carry row 1's rejected edit with it.
        assert await _title(first) == "Alpha"


class TestALostRaceIsOneRowsSkipNotTheFilesFailure:
    async def test_a_duplicate_inserted_at_the_same_moment_skips_that_row_and_the_rest_apply(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, w = world
        original = publishing.create_job

        async def loses_the_race_on_one_title(db, tenant_id, payload, **kwargs):  # type: ignore[no-untyped-def]
            if payload.title == "Racer":
                raise IntegrityError("INSERT INTO jobs", {}, Exception("duplicate external_ref"))
            return await original(db, tenant_id, payload, **kwargs)

        monkeypatch.setattr(publishing, "create_job", loses_the_race_on_one_title)

        body = await _upload(client, w, "external_ref,title\nA1,Before\nA2,Racer\nA3,After\n")

        assert [r["status"] for r in body["rows"]] == ["warning", "skip", "warning"]
        assert [r["created"] for r in body["rows"]] == [True, False, True]
        assert "same moment" in body["rows"][1]["messages"][0]
        # And the whole thing was recorded, which also reads the organisation after the rollback.
        async with get_sessionmaker()() as db:
            titles = set(
                (
                    await db.scalars(
                        select(Job.title).where(Job.title.in_(["Before", "Racer", "After"]))
                    )
                ).all()
            )
        assert titles == {"Before", "After"}
