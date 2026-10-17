"""`GET /jobs?sort=newest` and a page boundary that holds still (Sprint 75, ADR-085).

Sprint 74 stamped when a vacancy went live; this is what that date is for. The default stays the
title, so the released app is untouched, and a vacancy published before the date existed sorts
after every dated one rather than by its draft's date (that would be an invented posting date).
`_paged` also gains a unique tie-break: ordered by a title alone, two equal titles could swap
between page one and page two.
"""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.marketplace.models import Job
from tests.moderation_support import make_skill, organisation, published_job


async def _jobs(
    client: AsyncClient, db: AsyncSession, titles: list[str]
) -> tuple[str, list[dict[str, object]]]:
    headers, org = await organisation(client, db)
    skill = await make_skill(db)
    return org, [await published_job(client, headers, org, skill, title) for title in titles]


def _titles(response_json: dict) -> list[str]:
    return [j["title"] for j in response_json["items"]]


async def _set_dates(db: AsyncSession, dated: dict[str, datetime | None]) -> None:
    for slug, when in dated.items():
        await db.execute(update(Job).where(Job.slug == slug).values(published_at=when))
    await db.commit()


class TestNewestFirst:
    async def test_the_newest_posted_comes_first_and_undated_ones_come_last(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        tag = uuid.uuid4().hex[:8]
        _, made = await _jobs(
            client,
            db,
            [f"Sort {tag} Delta", f"Sort {tag} Alpha", f"Sort {tag} Charlie", f"Sort {tag} Bravo"],
        )
        by_title = {j["title"]: str(j["slug"]) for j in made}
        now = datetime.now(UTC)
        await _set_dates(
            db,
            {
                by_title[f"Sort {tag} Delta"]: now - timedelta(days=1),
                by_title[f"Sort {tag} Alpha"]: now - timedelta(days=9),
                by_title[f"Sort {tag} Charlie"]: None,
                by_title[f"Sort {tag} Bravo"]: None,
            },
        )

        newest = (await client.get("/jobs", params={"q": f"Sort {tag}", "sort": "newest"})).json()
        title = (await client.get("/jobs", params={"q": f"Sort {tag}"})).json()

        assert _titles(newest) == [
            f"Sort {tag} Delta",  # yesterday
            f"Sort {tag} Alpha",  # nine days ago
            f"Sort {tag} Bravo",  # undated, by title
            f"Sort {tag} Charlie",
        ]
        # The default is unchanged: by title.
        assert _titles(title) == sorted(_titles(title))

    async def test_an_unknown_sort_is_refused(self, client: AsyncClient) -> None:
        assert (await client.get("/jobs", params={"sort": "random"})).status_code == 422

    async def test_the_default_is_the_title_with_or_without_saying_so(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        tag = uuid.uuid4().hex[:8]
        await _jobs(client, db, [f"Order {tag} B", f"Order {tag} A", f"Order {tag} C"])
        bare = (await client.get("/jobs", params={"q": f"Order {tag}"})).json()
        said = (await client.get("/jobs", params={"q": f"Order {tag}", "sort": "title"})).json()
        assert (
            _titles(bare) == _titles(said) == [f"Order {tag} A", f"Order {tag} B", f"Order {tag} C"]
        )


class TestAPageBoundaryThatHoldsStill:
    async def test_equal_titles_and_dates_come_back_in_id_order_on_every_sort(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        tag = uuid.uuid4().hex[:8]
        _, made = await _jobs(client, db, [f"Same {tag}"] * 6)
        when = datetime.now(UTC) - timedelta(days=2)
        await _set_dates(db, {str(j["slug"]): when for j in made})
        ids = sorted(str(j["id"]) for j in made)

        for sort in ("title", "newest"):
            got: list[str] = []
            for offset in range(6):  # one at a time: the boundary is crossed five times
                page = (
                    await client.get(
                        "/jobs",
                        params={"q": f"Same {tag}", "sort": sort, "limit": 1, "offset": offset},
                    )
                ).json()
                got.append(str(page["items"][0]["id"]))
            assert got == ids, f"sort={sort}: the same six, once each, in id order"
