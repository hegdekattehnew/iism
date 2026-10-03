"""Reading `application_reviews` back (Sprint 41).

Sprint 37 built the writer for a two-sided rating and nothing that read it, so
a rating could be given and never seen. This is the reader, kept apart from
`review_service.py` (which writes) so that `service.py` and `employer_service.py`
can import it without the cycle `review_service` -> `employer_service` would make.

**What it never does is put a rating on a candidate card.** ADR-037 keeps
every employer-facing candidate payload de-identified, and a worker's rating is
a fact about one person. A worker sees their own; an employer's poster rating is
public, because a worker choosing whom to work for is exactly who it is for.

An average over no ratings is `None`, never 0.0: "no ratings yet" and "rated
badly" are different things, and the interface must not draw the first as the
second.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.applications.models import Application, ApplicationReview
from api.modules.marketplace.models import Job, posted_job


@dataclass(frozen=True)
class Reputation:
    average: float
    count: int


def _reputation(average: object, count: int) -> Reputation | None:
    if not count or average is None:
        return None
    return Reputation(average=round(float(average), 1), count=count)  # type: ignore[arg-type]


async def reviewed_ids(
    db: AsyncSession, application_ids: Iterable[uuid.UUID], subject_role: str
) -> set[uuid.UUID]:
    """Which of these applications already carry a review in this direction.

    One query for a whole list. `subject_role` names who the review is *about*,
    so `"worker"` answers "has the employer rated this worker" and `"poster"`
    answers "has this worker rated the employer".
    """
    ids = list(application_ids)
    if not ids:
        return set()
    rows = await db.scalars(
        select(ApplicationReview.application_id).where(
            ApplicationReview.application_id.in_(ids),
            ApplicationReview.subject_role == subject_role,
        )
    )
    return set(rows.all())


async def poster_reputation(db: AsyncSession, tenant_id: uuid.UUID) -> Reputation | None:
    """How workers rated this organisation, across every vacancy it has posted."""
    row = (
        await db.execute(
            select(func.avg(ApplicationReview.rating), func.count(ApplicationReview.id))
            .select_from(ApplicationReview)
            .join(Application, Application.id == ApplicationReview.application_id)
            .join(Job, Job.id == Application.job_id)
            .where(Job.tenant_id == tenant_id, ApplicationReview.subject_role == "poster")
        )
    ).one()
    return _reputation(row[0], row[1])


async def poster_reputation_for_job(db: AsyncSession, job_slug: str) -> Reputation | None:
    """The poster's rating, found from a vacancy's public address.

    `None` for a vacancy that is not published as well as for one with no
    ratings, so the endpoint cannot be used to learn that a draft exists.
    """
    tenant_id = await db.scalar(select(Job.tenant_id).where(Job.slug == job_slug, posted_job()))
    if tenant_id is None:
        return None
    return await poster_reputation(db, tenant_id)


async def worker_reputation(db: AsyncSession, profile_id: uuid.UUID) -> Reputation | None:
    """How employers rated this candidate's finished work. Their own to see."""
    row = (
        await db.execute(
            select(func.avg(ApplicationReview.rating), func.count(ApplicationReview.id))
            .select_from(ApplicationReview)
            .join(Application, Application.id == ApplicationReview.application_id)
            .where(Application.profile_id == profile_id, ApplicationReview.subject_role == "worker")
        )
    ).one()
    return _reputation(row[0], row[1])
