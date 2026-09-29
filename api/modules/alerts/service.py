"""Telling a candidate about a vacancy they did not go looking for.

**The largest reach gap this product had.** `match_jobs` is called from one
request handler, so for twenty-six sprints a vacancy published on Monday
reached a matched candidate only if they happened to open `/matches`. The
scoring, the outbox and the worker all existed; nothing joined them up.

Three things make this honest rather than a spam cannon:

* **One scorer** (ADR-037). The sweep ranks candidates through
  `matching.candidates_for_job`, the same `score_match` the employer console
  runs. A second, looser "is this close enough to email about" rule would be
  the second scorer this project has refused twice.
* **Told once, ever.** `JobAlert` has a unique `(job_id, profile_id)`, and the
  job is claimed by stamping `alerted_at` before anything is queued. A sweep
  that runs twice in a minute finds nothing the second time.
* **Caps at both ends.** At most `MAX_PER_JOB` people hear about any one
  vacancy, and at most `MAX_PER_CANDIDATE_PER_DAY` vacancies reach any one
  person. Without the second, a Monday morning of forty new listings is forty
  notifications, which is how somebody stops reading all of them.

**In-app is the channel that actually lands**, and that is worth stating
plainly rather than discovering: 39 of 40 seeded candidates signed up with a
phone and have no email address at all, and SMS waits on DLT registration.
Email is queued too, for the minority who have one; the rest see it on the
site, which is a smaller promise than "we will alert you" and the true one.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.modules.alerts.models import JobAlert
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, Job, open_job
from api.modules.matching.scoring import SERIOUS_MATCH_SCORE as MIN_SCORE
from api.modules.notifications import enqueue

log = structlog.get_logger("iism.alerts")

# How many vacancies one sweep will consider. The cron runs often; a backlog
# drains over a few minutes rather than in one long transaction.
MAX_JOBS_PER_SWEEP = 10


@dataclass(frozen=True)
class SweepResult:
    """What one run did. Returned so the cron can log it and tests can assert."""

    jobs: int = 0
    alerts: int = 0
    skipped_capped: int = 0
    skipped_opted_out: int = 0


async def _recent_alert_counts(
    db: AsyncSession, profile_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """How many alerts each of these people has had in the last 24 hours.

    One grouped query rather than one per candidate: a sweep over ten jobs
    against a pool of a few hundred would otherwise be a few hundred
    round-trips to answer a question with one answer per person.
    """
    if not profile_ids:
        return {}
    since = datetime.now(UTC) - timedelta(days=1)
    rows = await db.execute(
        select(JobAlert.profile_id, func.count())
        .where(JobAlert.profile_id.in_(profile_ids), JobAlert.created_at >= since)
        .group_by(JobAlert.profile_id)
    )
    return dict(rows.all())  # type: ignore[arg-type]


async def _already_told(db: AsyncSession, job_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await db.scalars(select(JobAlert.profile_id).where(JobAlert.job_id == job_id))
    return set(rows.all())


async def _users_by_id(db: AsyncSession, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    """One query per job rather than one per eligible candidate -- ten jobs
    against twenty-five candidates each was up to 250 individual lookups."""
    if not user_ids:
        return {}
    rows = await db.scalars(select(User).where(User.id.in_(user_ids)))
    return {u.id: u for u in rows.all()}


async def sweep(db: AsyncSession, *, limit: int = MAX_JOBS_PER_SWEEP) -> SweepResult:
    """Alert matched candidates about vacancies nobody has been told about yet.

    Called by the worker, never by a request handler: it scores a pool and
    queues mail, which is not work to do while somebody waits for a page.
    """
    settings = get_settings()
    # Imported inside the function: `matching` imports `applications`, which
    # imports `marketplace`; a module-level import here is an ImportError at
    # boot rather than a wrong answer, and `tests/test_import_order.py` is what
    # catches that.
    from api.modules.matching import candidates_for_job

    jobs = list(
        (
            await db.scalars(
                select(Job)
                .where(open_job(), Job.alerted_at.is_(None))
                .order_by(Job.created_at)
                .limit(limit)
            )
        ).all()
    )
    if not jobs:
        return SweepResult()

    now = datetime.now(UTC)
    alerts = capped = opted_out = 0

    for job in jobs:
        # **Claim the job first.** Stamped before anything is queued, so a
        # crash halfway through costs the rest of this vacancy's alerts rather
        # than sending the first few again on the next run. Under-alerting is
        # recoverable by hand; double-alerting is not.
        job.alerted_at = now

        scored = await candidates_for_job(db, job)
        eligible = [c for c in scored if c.result.score >= MIN_SCORE]
        if not eligible:
            continue

        told = await _already_told(db, job.id)
        profile_ids = [c.profile.id for c in eligible if c.profile.id not in told]
        recent = await _recent_alert_counts(db, profile_ids)
        users = await _users_by_id(db, {c.profile.user_id for c in eligible})

        sent_for_this_job = 0
        for candidate in eligible:
            if sent_for_this_job >= settings.max_alerts_per_job:
                break
            profile = candidate.profile
            if profile.id in told:
                continue
            if not profile.job_alerts_enabled:
                opted_out += 1
                continue
            if recent.get(profile.id, 0) >= settings.max_alerts_per_candidate_per_day:
                capped += 1
                continue

            user = users.get(profile.user_id)
            if user is None:
                continue

            payload = {
                "vacancy": job.title,
                "organisation": _organisation_name(job),
                "path": f"/jobs/{job.slug}",
            }
            # In-app always; email only where there is one. Two rows rather
            # than one so the outbox's own `skipped` count stays meaningful --
            # a candidate with no address is not a failure.
            await enqueue(
                db,
                recipient_kind="user",
                recipient_id=user.id,
                channel="in_app",
                template="job_alert",
                payload=payload,
                locale=user.preferred_locale,
            )
            if user.email:
                await enqueue(
                    db,
                    recipient_kind="user",
                    recipient_id=user.id,
                    channel="email",
                    template="job_alert",
                    payload=payload,
                    locale=user.preferred_locale,
                )
            db.add(JobAlert(job_id=job.id, profile_id=profile.id))
            recent[profile.id] = recent.get(profile.id, 0) + 1
            alerts += 1
            sent_for_this_job += 1

    await db.commit()
    result = SweepResult(
        jobs=len(jobs), alerts=alerts, skipped_capped=capped, skipped_opted_out=opted_out
    )
    if alerts or capped:
        log.info("alerts.swept", **result.__dict__)
    return result


def _organisation_name(job: Job) -> str:
    """`Job.tenant` is typed `object` on the model; the cast is at the read."""
    tenant = job.tenant
    return tenant.name if isinstance(tenant, Tenant) else ""


async def close_expired(db: AsyncSession, *, limit: int = 200) -> int:
    """Close vacancies whose closing date has passed. Returns how many.

    **In the worker, not in a request.** A closing date enforced only when
    somebody happens to load the page is not a closing date -- the vacancy
    would stay in browse and in matches until a visitor arrived, and two people
    loading it a second apart would see different answers.
    """
    now = datetime.now(UTC)
    jobs = list(
        (
            await db.scalars(
                select(Job)
                .where(open_job(), Job.closes_at.is_not(None), Job.closes_at <= now)
                .limit(limit)
            )
        ).all()
    )
    for job in jobs:
        job.closed_at = now
        job.close_reason = "expired"
    if jobs:
        await db.commit()
        log.info("marketplace.jobs_expired", count=len(jobs))
    return len(jobs)


async def alert_preference(db: AsyncSession, profile: CandidateProfile, enabled: bool) -> None:
    """Turn alerts on or off for one candidate."""
    profile.job_alerts_enabled = enabled
    await db.commit()
