"""Hire and train: an employer offers to sponsor the one missing standard (ADR-048).

The employer's console already shows the candidates who are missing exactly one
mandatory standard, and names the standard. This is what it can do about it:
see the courses that teach it, and offer to sponsor one. The candidate gets a
single in-app notice and the vacancy's page, where applying is the act that
discloses them -- so the employer learns who they are only because the
candidate chose to apply, exactly as ADR-037 already requires.

**Four rules, each load-bearing.**

* *A reference is a handle, not a key.* `C-XXXXXXXX` is the first eight hex
  characters of a profile id. It is resolved here, server-side, and only inside
  this vacancy's own near-miss pool -- never as a lookup of its own, so it
  cannot be used to probe for profiles that are not in that pool.
* *The same ranking the console uses.* The pool comes from `candidates_for_job`,
  which is `score_match` (ADR-037). A looser "who deserves an offer" rule would
  be a second scorer.
* *Unsolicited, so it obeys the alerts' rules.* A candidate who switched off
  job alerts is not messaged, and an offer counts against the same daily cap an
  alert does.
* *The employer is never told which.* An opted-out or capped candidate and a
  notified one produce the same response, because an opt-out is a fact about the
  candidate and must not leak through an employer-facing endpoint.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.modules.alerts.models import JobAlert, SponsorIntent
from api.modules.analytics import record
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import Job, open_job
from api.modules.matching import (
    CourseSuggestion,
    candidate_card,
    candidates_for_job,
    courses_closing_gap,
)
from api.modules.matching.scoring import MissingSkill
from api.modules.notifications import enqueue

log = structlog.get_logger("iism.alerts")


@dataclass(frozen=True)
class TrainingOffer:
    """The one missing standard, the courses that teach it, and whether this
    organisation has already made an offer."""

    reference: str
    standard: MissingSkill
    courses: list[CourseSuggestion]
    offered: bool


async def _near_miss(
    db: AsyncSession, tenant_id: uuid.UUID, job_slug: str, reference: str
) -> tuple[Job, Any, MissingSkill]:
    """The vacancy, and the one candidate in its near-miss pool this reference names.

    `open_job()`, not merely published: offering to train someone for a vacancy
    that has been filled or has expired is an offer to nobody. 404 for every way
    this can fail -- an unknown vacancy, a reference outside the pool, a
    candidate who is not actually one standard short -- so the answer reveals
    nothing about which of them it was.
    """
    job = await db.scalar(
        select(Job).where(Job.slug == job_slug, Job.tenant_id == tenant_id, open_job())
    )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    pool = await candidates_for_job(db, job)
    # Eight hex characters can in principle collide; an ambiguous reference is
    # treated as not found rather than guessed at.
    named = [
        c
        for c in pool
        if c.result.missing_mandatory == 1
        and candidate_card(c.profile, c.result).reference == reference.upper()
    ]
    if len(named) != 1:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    candidate = named[0]
    standard = next(m for m in candidate.result.missing if m.is_mandatory)
    return job, candidate, standard


async def training_for(
    db: AsyncSession, tenant_id: uuid.UUID, job_slug: str, reference: str
) -> TrainingOffer:
    """What an employer sees before deciding: the standard and its courses."""
    job, candidate, standard = await _near_miss(db, tenant_id, job_slug, reference)
    courses = await courses_closing_gap(db, [standard])
    already = await db.scalar(
        select(SponsorIntent.id).where(
            SponsorIntent.job_id == job.id, SponsorIntent.profile_id == candidate.profile.id
        )
    )
    return TrainingOffer(
        reference=reference.upper(), standard=standard, courses=courses, offered=already is not None
    )


async def _may_message(db: AsyncSession, profile_id: uuid.UUID, opted_in: bool) -> bool:
    """Whether an unsolicited notice may be queued for this candidate now.

    The alerts' own two rules: the opt-out, and the daily cap -- which an offer
    shares with the alerts it sits beside, so a busy day of either cannot be the
    reason somebody stops reading.
    """
    if not opted_in:
        return False
    since = datetime.now(UTC) - timedelta(days=1)
    alerts = (
        await db.scalar(
            select(func.count())
            .select_from(JobAlert)
            .where(JobAlert.profile_id == profile_id, JobAlert.created_at >= since)
        )
    ) or 0
    offers = (
        await db.scalar(
            select(func.count())
            .select_from(SponsorIntent)
            .where(
                SponsorIntent.profile_id == profile_id,
                SponsorIntent.notified_at.is_not(None),
                SponsorIntent.created_at >= since,
            )
        )
    ) or 0
    return alerts + offers < get_settings().max_alerts_per_candidate_per_day


async def offer(
    db: AsyncSession,
    tenant: Tenant,
    job_slug: str,
    reference: str,
    *,
    actor_user_id: uuid.UUID,
) -> SponsorIntent:
    """Record the offer, and tell the candidate if they may be told.

    Once per (vacancy, candidate): a second offer is a 409, and so is losing the
    race to a double click, because the unique constraint is the real guard and
    the pre-check is only the friendly answer.

    Refused (422) when no course teaches the standard. An offer to sponsor
    training that does not exist is a promise nobody can keep, and the notice
    would have nothing to name.
    """
    job, candidate, standard = await _near_miss(db, tenant.id, job_slug, reference)
    profile = candidate.profile

    existing = await db.scalar(
        select(SponsorIntent.id).where(
            SponsorIntent.job_id == job.id, SponsorIntent.profile_id == profile.id
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already made this offer")

    courses = await courses_closing_gap(db, [standard])
    if not courses:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No course on the platform teaches this standard yet",
        )

    notify = await _may_message(db, profile.id, profile.job_alerts_enabled)
    user = await db.get(User, profile.user_id) if notify else None
    intent = SponsorIntent(
        job_id=job.id,
        profile_id=profile.id,
        skill_id=standard.skill_id,
        offered_by_user_id=actor_user_id,
        notified_at=datetime.now(UTC) if user is not None else None,
    )
    db.add(intent)
    if user is not None:
        await enqueue(
            db,
            recipient_kind="user",
            recipient_id=user.id,
            channel="in_app",
            template="sponsor_offer",
            # The organisation, the standard and the course. Nothing about the
            # candidate beyond that they are the recipient, and no score: this
            # is an invitation to look at a vacancy, not a verdict.
            payload={
                "vacancy": job.title,
                "organisation": tenant.name,
                "standard": standard.name,
                "course": courses[0].course.title,
                "path": f"/jobs/{job.slug}",
            },
            locale=user.preferred_locale,
        )
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already made this offer") from error

    # After the commit and outside it (`record()` commits). Subject to the
    # vacancy, never the candidate.
    await record(
        db,
        "sponsor_intent_recorded",
        user_id=actor_user_id,
        subject_type="job",
        subject_id=job.id,
        payload={"notified": intent.notified_at is not None},
    )
    return intent
