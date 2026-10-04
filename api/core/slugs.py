"""Inserting a row whose slug was chosen from a read.

`unique_slug` and `_unique_tenant_slug` read the slugs already taken and pick the
first free one, and the row carrying it is inserted *afterwards*. Two requests for
the same name each see the slug free, each pick it, and the unique index refuses the
second -- which used to surface as a 500 (Sprint 46). It is the likeliest of the
check-then-write races to be hit by one person: an employer double-tapping "Create
vacancy" posts the same title and district a few milliseconds apart.

The unique index is the arbiter, as it is for a duplicate application (ADR-052); this
is the loop around it. A collision is not a failure -- somebody else took that slug a
moment ago -- so the loser chooses again, and the next read sees the winner's row.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Each attempt loses only to a request that committed since the last read, so five
# is generous: it takes five people choosing the same name inside one round trip.
MAX_SLUG_ATTEMPTS = 5


async def add_with_unique_slug[Row](
    db: AsyncSession,
    column: Any,
    choose: Callable[[], Awaitable[str]],
    build: Callable[[str], Row],
    *,
    after_collision: Callable[[], Awaitable[None]] | None = None,
) -> Row:
    """Choose a slug, insert the row, and choose again if somebody beat us to it.

    * `choose` returns a free slug (and is called again after every collision, so it
      reads what the winner committed).
    * `build` makes the row for a slug. A new instance each attempt: the failed one is
      expelled from the session along with its savepoint.
    * `after_collision` runs after a lost race and may raise. Organisation creation
      uses it to re-ask "is this the same person's other tap?" -- if so the answer is
      the duplicate refusal, not a second organisation called `x-2`.

    The insert is in a savepoint, so losing undoes only itself. An `IntegrityError`
    is treated as a collision **only if the slug is now taken**; any other violation
    (a foreign key, say) is raised as it was, rather than retried into a misleading
    "try again".
    """
    for _ in range(MAX_SLUG_ATTEMPTS):
        slug = await choose()
        row = build(slug)
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
            return row
        except IntegrityError:
            taken = await db.scalar(select(column).where(column == slug).limit(1))
            if taken is None:
                raise
            if after_collision is not None:
                await after_collision()
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        "Several people chose the same name at once. Please try again.",
    )
