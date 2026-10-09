"""Queueing many notices at once (Sprint 52).

Erasing an organisation tells every applicant still waiting on it. That used to build one ORM
object per applicant inside the deleting request; `enqueue_many` writes the same rows as batched
multi-row INSERTs. What is worth pinning is that it is the *same rows*, and that it survives a
number of recipients that would break a naive statement.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.notifications import enqueue, enqueue_many
from api.modules.notifications.models import Notification


def _notice(recipient: uuid.UUID, **over: object) -> dict[str, object]:
    return {
        "recipient_kind": "user",
        "recipient_id": recipient,
        "channel": "in_app",
        "template": "vacancy_closed",
        "payload": {"vacancy": "Ward assistant", "path": "/applications"},
        **over,
    }


async def test_it_writes_the_rows_enqueue_would_have_written(db: AsyncSession) -> None:
    one, two = uuid.uuid4(), uuid.uuid4()
    await enqueue(
        db,
        recipient_kind="user",
        recipient_id=one,
        channel="in_app",
        template="vacancy_closed",
        payload={"vacancy": "Ward assistant", "path": "/applications"},
    )
    assert await enqueue_many(db, [_notice(two)]) == 1
    await db.flush()

    singly, in_bulk = [
        (await db.scalars(select(Notification).where(Notification.recipient_id == r))).one()
        for r in (one, two)
    ]
    for field in (
        "recipient_kind",
        "channel",
        "template",
        "payload",
        "locale",
        "status",
        "attempts",
    ):
        assert getattr(in_bulk, field) == getattr(singly, field), field
    assert in_bulk.id != singly.id and in_bulk.created_at is not None


async def test_a_locale_may_be_given_and_defaults_to_english(db: AsyncSession) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    await enqueue_many(db, [_notice(a), _notice(b, locale="hi")])
    await db.flush()
    rows = {
        r.recipient_id: r.locale
        for r in (
            await db.scalars(select(Notification).where(Notification.recipient_id.in_([a, b])))
        ).all()
    }
    assert rows == {a: "en", b: "hi"}


async def test_nothing_to_send_is_not_an_error(db: AsyncSession) -> None:
    assert await enqueue_many(db, []) == 0


async def test_thousands_of_recipients_are_one_call_and_all_arrive(db: AsyncSession) -> None:
    """asyncpg refuses more than 32,767 bind parameters in one statement (CLAUDE.md); a few
    thousand notices of six columns each would pass that if they were sent as one literal."""
    marker = f"bulk-{uuid.uuid4().hex[:8]}"
    notices = [_notice(uuid.uuid4(), payload={"marker": marker}) for _ in range(6_000)]

    assert await enqueue_many(db, notices) == 6_000
    await db.flush()

    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.payload["marker"].astext == marker)
    )
    assert count == 6_000
