"""A vacancy's posted date is stamped at every writer of "published" and never invented
(Sprint 74, ADR-084).

`created_at` is the draft's date, so "posted 3 days ago" needs its own column, and a column is only
as true as the writers that keep it. This pins each one: publishing stamps, unpublishing and a
takedown clear, saving a live vacancy again or reopening a closed one leaves the date alone, a bulk
publish goes through the same function, and a vacancy published before the column existed says
nothing instead of something made up.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.marketplace.models import Job
from tests.moderation_support import make_skill, operator, organisation, published_job


def _parse(value: str | None) -> datetime:
    assert value is not None
    return datetime.fromisoformat(value)


async def _draft(client: AsyncClient, headers: dict[str, str], org: str, skill: str) -> str:
    created = await client.post(
        f"/org/{org}/jobs",
        headers=headers,
        json={
            "title": "Posted-date vacancy",
            "skills": [{"skill_slug": skill, "importance": 4, "is_mandatory": True}],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["published_at"] is None  # a draft was never posted
    return str(created.json()["slug"])


async def _owner_view(client: AsyncClient, headers: dict[str, str], org: str, slug: str) -> dict:
    response = await client.get(f"/org/{org}/jobs/{slug}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestPublishing:
    async def test_publishing_stamps_now_and_the_public_page_carries_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        before = datetime.now(UTC)
        job = await published_job(client, headers, org, await make_skill(db))

        stamped = _parse(job["published_at"])  # type: ignore[arg-type]
        assert before - timedelta(seconds=5) <= stamped <= datetime.now(UTC) + timedelta(seconds=5)
        assert (await client.get(f"/jobs/{job['slug']}")).json()["published_at"] == (
            job["published_at"]
        )
        listed = (await client.get("/jobs", params={"limit": 50})).json()["items"]
        assert {j["slug"]: j["published_at"] for j in listed}[job["slug"]] == job["published_at"]

    async def test_publishing_a_vacancy_that_is_already_live_does_not_move_its_date(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        again = await client.post(f"/org/{org}/jobs/{job['slug']}/publish", headers=headers)
        assert again.status_code == 200
        assert again.json()["published_at"] == job["published_at"]

    async def test_unpublishing_clears_it_and_publishing_again_stamps_a_new_one(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        slug = str(job["slug"])
        # Back-date the first posting so "a new one" is visible without sleeping.
        await db.execute(
            update(Job)
            .where(Job.slug == slug)
            .values(published_at=datetime.now(UTC) - timedelta(days=9))
        )
        await db.commit()

        down = await client.post(f"/org/{org}/jobs/{slug}/unpublish", headers=headers)
        assert down.status_code == 200 and down.json()["published_at"] is None

        up = await client.post(f"/org/{org}/jobs/{slug}/publish", headers=headers)
        assert up.status_code == 200
        assert datetime.now(UTC) - _parse(up.json()["published_at"]) < timedelta(minutes=1)

    async def test_a_bulk_publish_stamps_each_vacancy(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        skill = await make_skill(db)
        slugs = [await _draft(client, headers, org, skill) for _ in range(2)]
        bulk = await client.post(
            f"/org/{org}/jobs/bulk/publish", headers=headers, json={"slugs": slugs}
        )
        assert bulk.status_code == 200 and all(r["published"] for r in bulk.json()["results"])
        for slug in slugs:
            view = await _owner_view(client, headers, org, slug)
            assert datetime.now(UTC) - _parse(view["published_at"]) < timedelta(minutes=1)


class TestReopeningIsNotAReposting:
    async def test_closing_and_reopening_keeps_the_original_date(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        slug = str(job["slug"])
        old = datetime.now(UTC) - timedelta(days=12)
        await db.execute(update(Job).where(Job.slug == slug).values(published_at=old))
        await db.commit()

        closed = await client.post(f"/org/{org}/jobs/{slug}/close", headers=headers, json={})
        assert closed.status_code == 200, closed.text
        assert _parse(closed.json()["published_at"]) == old  # closing is not unpublishing
        reopened = await client.post(f"/org/{org}/jobs/{slug}/reopen", headers=headers)
        assert reopened.status_code == 200, reopened.text
        assert _parse(reopened.json()["published_at"]) == old


class TestATakedown:
    async def test_it_clears_the_date_and_a_restored_draft_is_published_again_by_its_owner(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        slug = str(job["slug"])
        ops = await operator(client, db, "admin")

        taken = await client.post(
            f"/ops/listings/job/{job['id']}/takedown",
            headers=ops,
            json={"reason": "It asked applicants to pay a fee before an interview."},
        )
        assert taken.status_code == 200, taken.text
        assert (await _owner_view(client, headers, org, slug))["published_at"] is None

        restored = await client.post(f"/ops/listings/job/{job['id']}/restore", headers=ops)
        assert restored.status_code == 200, restored.text
        # Restored as a draft: still not posted, so still no date.
        assert (await _owner_view(client, headers, org, slug))["published_at"] is None

        up = await client.post(f"/org/{org}/jobs/{slug}/publish", headers=headers)
        assert up.status_code == 200 and up.json()["published_at"] is not None


class TestAVacancyFromBeforeTheColumn:
    async def test_it_says_nothing_rather_than_something_made_up(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        await db.execute(update(Job).where(Job.slug == job["slug"]).values(published_at=None))
        await db.commit()

        body = (await client.get(f"/jobs/{job['slug']}")).json()
        assert body["published_at"] is None
        assert body["is_open"] is True  # and it is still a live, ordinary vacancy
        row = await db.scalar(select(Job).where(Job.slug == job["slug"]))
        assert row is not None and row.published_at is None


class TestTheSeeds:
    """The seeds build `Job` rows directly, so they are writers of "published" the services never
    see (the model's default status is `published`)."""

    ROOT = Path(__file__).resolve().parent.parent / "scripts"

    def test_every_seeded_publication_is_dated(self) -> None:
        for name in ("seed_marketplace.py", "seed_sector_expansion.py"):
            source = (self.ROOT / name).read_text(encoding="utf-8")
            published = source.count('job.status = "published"')
            dated = source.count("job.published_at = job.published_at or _posted_at(slug)")
            assert published >= 1, name  # found the writer before judging it
            assert dated == published, f"{name}: {published} job(s) published, {dated} dated"

    def test_the_scale_seed_dates_its_raw_insert(self) -> None:
        source = (self.ROOT / "seed_scale.py").read_text(encoding="utf-8")
        assert "nsqf_level_min, status, positions, published_at)" in source

    def test_a_seeded_date_is_recent_stable_and_spread(self) -> None:
        import sys

        sys.path.insert(0, str(self.ROOT))
        from seed_marketplace import _posted_at

        def age_in_days(slug: str) -> int:
            posted = _posted_at(slug)  # read first: the clock only moves forward
            return round((datetime.now(UTC) - posted).total_seconds() / 86400)

        slugs = [f"seed-slug-{i}" for i in range(200)]
        ages = [age_in_days(s) for s in slugs]
        assert min(ages) == 0 and max(ages) == 21  # the whole range is used, and no further
        assert ages == [age_in_days(s) for s in slugs]  # a slug's age does not drift between runs
