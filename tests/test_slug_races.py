"""Sprint 46: two requests choosing the same slug.

`unique_slug` and `_unique_tenant_slug` read the slugs already taken and pick the
first free one; the row carrying it is inserted afterwards. Two requests for the
same name each see the slug free, each pick it, and the unique constraint refuses
the second -- with nothing to catch it, a **500**.

This is the same shape as Sprint 45's double-submit, and it is the likeliest of
them to be hit by one person: an employer double-tapping "Create vacancy" posts
two vacancies with the same title and district a few milliseconds apart.

The loser should not be told it failed. A second vacancy with the same title is
legitimate (two sites, two shifts) and takes the next free suffix; a second
organisation **by the same person** with the same name is the duplicate Sprint 26
refuses, and gets that refusal.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_sessionmaker
from api.core.slugs import add_with_unique_slug
from api.modules.identity.models import Membership, Tenant
from tests.concurrency import World, build_world, candidate, real_client, tear_down


@pytest.fixture
async def world() -> AsyncIterator[tuple[AsyncClient, World]]:
    async with real_client() as client:
        built = await build_world(client)
        try:
            yield client, built
        finally:
            await tear_down(client, built)


def _slow(module: object, name: str, monkeypatch: pytest.MonkeyPatch, seconds: float = 0.4) -> None:
    """Hold the slug helper open after it answers, so both requests have chosen
    before either inserts."""
    original = getattr(module, name)

    async def slow(*args: object, **kwargs: object) -> object:
        result = await original(*args, **kwargs)
        await asyncio.sleep(seconds)
        return result

    monkeypatch.setattr(module, name, slow)


class TestListings:
    async def test_two_vacancies_with_one_title_at_once_both_succeed_with_different_slugs(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.marketplace import publishing

        client, built = world
        _slow(publishing, "unique_slug", monkeypatch)
        body = {
            "title": "Race Cashier",
            "location_district": "Pune",
            "skills": [{"skill_slug": built.skill_slug, "importance": 3}],
        }

        a, b = await asyncio.gather(
            client.post(f"/org/{built.employer_slug}/jobs", headers=built.employer, json=body),
            client.post(f"/org/{built.employer_slug}/jobs", headers=built.employer, json=body),
        )

        assert a.status_code == b.status_code == 201, (a.text, b.text)
        assert a.json()["slug"] != b.json()["slug"]

    async def test_two_courses_with_one_title_at_once_both_succeed_with_different_slugs(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.marketplace import course_publishing

        client, built = world
        _slow(course_publishing, "unique_slug", monkeypatch)
        body = {
            "title": "Race Course",
            "skills": [{"skill_slug": built.skill_slug, "level_taught": 3}],
        }

        a, b = await asyncio.gather(
            client.post(f"/org/{built.provider_slug}/courses", headers=built.provider, json=body),
            client.post(f"/org/{built.provider_slug}/courses", headers=built.provider, json=body),
        )

        assert a.status_code == b.status_code == 201, (a.text, b.text)
        assert a.json()["slug"] != b.json()["slug"]


class TestOrganisations:
    async def test_two_people_naming_an_organisation_alike_at_once_both_succeed(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.identity import service

        client, built = world
        first, second = await candidate(client), await candidate(client)
        built.candidates += [first, second]
        _slow(service, "_unique_tenant_slug", monkeypatch)
        body = {"organisation_name": "Race Kitchens Ltd", "tenant_type": "employer"}

        a, b = await asyncio.gather(
            client.post("/me/organisations", headers=first, json=body),
            client.post("/me/organisations", headers=second, json=body),
        )

        assert a.status_code == b.status_code == 201, (a.text, b.text)
        assert a.json()["slug"] != b.json()["slug"]

    async def test_one_person_double_tapping_gets_one_organisation_and_the_duplicate_refusal(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.identity import service

        client, built = world
        headers = await candidate(client)
        built.candidates.append(headers)
        _slow(service, "_unique_tenant_slug", monkeypatch)
        body = {"organisation_name": "Race Double Tap Ltd", "tenant_type": "employer"}

        a, b = await asyncio.gather(
            client.post("/me/organisations", headers=headers, json=body),
            client.post("/me/organisations", headers=headers, json=body),
        )

        assert sorted([a.status_code, b.status_code]) == [201, 409], (a.text, b.text)
        me = (await client.get("/auth/me", headers=headers)).json()
        owned = [m for m in me["memberships"] if m["tenant"]["name"] == "Race Double Tap Ltd"]
        assert len(owned) == 1
        async with get_sessionmaker()() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(Tenant)
                .join(Membership, Membership.tenant_id == Tenant.id)
                .where(Tenant.name == "Race Double Tap Ltd")
            )
        assert count == 1


class TestWhatIsNotACollision:
    async def test_a_violation_that_is_not_the_slug_is_raised_not_retried(
        self, db: AsyncSession
    ) -> None:
        """An invalid tenant type breaks a CHECK, an `IntegrityError` like any other.
        Retried five times and then reported as "several people chose the same name",
        it would send somebody round a loop for a fault no retry can fix -- so the
        helper only treats a violation as a collision if the slug is now taken."""

        async def choose() -> str:
            return "not-a-collision"

        with pytest.raises(IntegrityError):
            await add_with_unique_slug(
                db,
                Tenant.slug,
                choose,
                lambda slug: Tenant(slug=slug, name="Broken", tenant_type="not-a-type"),
            )
