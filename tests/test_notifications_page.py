"""The notification page's API (Sprint 60, BL-14.9): paging past fifty, a count, one notice read.

A cursor on time alone would be wrong here: `created_at` is the transaction's time, and an alert
sweep queues hundreds of notices in one transaction with the same timestamp. The tests make that
the usual case rather than the edge.
"""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.notifications.models import Notification
from tests.moderation_support import person


async def _notices(
    db: AsyncSession,
    user_id: uuid.UUID,
    n: int,
    *,
    same_time: bool = False,
    channel: str = "in_app",
    read: bool = False,
) -> list[Notification]:
    start = datetime.now(UTC) - timedelta(days=1)
    rows = [
        Notification(
            recipient_kind="user",
            recipient_id=user_id,
            channel=channel,
            template="vacancy_closed",
            payload={"vacancy": f"Job {i}", "path": "/applications"},
            created_at=start if same_time else start + timedelta(seconds=i),
            read_at=start if read else None,
        )
        for i in range(n)
    ]
    db.add_all(rows)
    await db.commit()
    return rows


async def _all_pages(client: AsyncClient, headers: dict[str, str], limit: int) -> list[dict]:
    seen: list[dict] = []
    params: dict[str, object] = {"limit": limit}
    for _ in range(50):
        page = (await client.get("/me/notifications", headers=headers, params=params)).json()
        seen += page
        if len(page) < limit:
            return seen
        params = {"limit": limit, "before": page[-1]["created_at"], "before_id": page[-1]["id"]}
    raise AssertionError("never ended")


class TestPaging:
    async def test_the_default_page_is_fifty_and_the_rest_is_reachable(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await person(client)
        await _notices(db, uid, 120)
        first = (await client.get("/me/notifications", headers=headers)).json()
        assert len(first) == 50
        assert len(await _all_pages(client, headers, 50)) == 120

    async def test_notices_sharing_a_timestamp_are_neither_skipped_nor_repeated(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await person(client)
        await _notices(db, uid, 130, same_time=True)
        pages = await _all_pages(client, headers, 40)
        ids = [n["id"] for n in pages]
        assert len(ids) == 130 and len(set(ids)) == 130

    async def test_the_limit_has_a_ceiling_and_a_floor(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, _ = await person(client)
        for bad in (0, 101):
            assert (
                await client.get("/me/notifications", headers=headers, params={"limit": bad})
            ).status_code == 422

    async def test_newest_first_and_read_ones_are_listed_too(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await person(client)
        await _notices(db, uid, 3, read=True)
        page = (await client.get("/me/notifications", headers=headers)).json()
        assert [n["payload"]["vacancy"] for n in page] == ["Job 2", "Job 1", "Job 0"]
        assert all(n["read_at"] for n in page)

    async def test_only_the_in_app_notices_of_this_person(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        mine, uid = await person(client)
        _, other = await person(client)
        await _notices(db, uid, 2)
        await _notices(db, uid, 3, channel="email")
        await _notices(db, other, 4)
        assert len((await client.get("/me/notifications", headers=mine)).json()) == 2

    async def test_signed_out_is_a_401(self, client: AsyncClient) -> None:
        assert (await client.get("/me/notifications")).status_code == 401
        assert (await client.get("/me/notifications/unread-count")).status_code == 401


class TestTheCountAndReadingOne:
    async def test_the_count_is_the_number_unread_and_nothing_else(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await person(client)
        _, other = await person(client)
        await _notices(db, uid, 3)
        await _notices(db, uid, 2, read=True)
        await _notices(db, uid, 5, channel="email")
        await _notices(db, other, 7)
        count = await client.get("/me/notifications/unread-count", headers=headers)
        assert count.json() == {"unread": 3}

    async def test_reading_one_lowers_the_count_by_one_and_is_idempotent(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await person(client)
        rows = await _notices(db, uid, 3)
        target = str(rows[0].id)
        assert (
            await client.post(f"/me/notifications/{target}/read", headers=headers)
        ).status_code == 204
        first = next(
            n
            for n in (await client.get("/me/notifications", headers=headers)).json()
            if n["id"] == target
        )["read_at"]
        assert first
        assert (
            await client.post(f"/me/notifications/{target}/read", headers=headers)
        ).status_code == 204
        again = next(
            n
            for n in (await client.get("/me/notifications", headers=headers)).json()
            if n["id"] == target
        )["read_at"]
        assert again == first, "reading twice does not move the time"
        assert (await client.get("/me/notifications/unread-count", headers=headers)).json() == {
            "unread": 2
        }

    async def test_somebody_elses_notice_or_an_unknown_one_is_a_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        mine, _ = await person(client)
        _, other = await person(client)
        (theirs,) = await _notices(db, other, 1)
        assert (
            await client.post(f"/me/notifications/{theirs.id}/read", headers=mine)
        ).status_code == 404
        assert (
            await client.post(f"/me/notifications/{uuid.uuid4()}/read", headers=mine)
        ).status_code == 404
        # ...and it was not read by the attempt.
        await db.refresh(theirs)
        assert theirs.read_at is None

    async def test_mark_all_read_still_works_and_zeroes_the_count(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await person(client)
        await _notices(db, uid, 4)
        assert (await client.post("/me/notifications/read", headers=headers)).json() == {
            "marked": 4
        }
        assert (await client.get("/me/notifications/unread-count", headers=headers)).json() == {
            "unread": 0
        }
