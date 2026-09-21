"""Match endpoints. Authenticated: a match is about a specific person."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.modules.analytics import record, record_many

# Candidate routes require a candidate, not merely a signed-in account: an
# organisation-only user used to get a CandidateProfile created on first look.
from api.modules.identity import get_current_candidate
from api.modules.identity.models import User
from api.modules.marketplace import ensure_profile
from api.modules.marketplace.models import CandidateProfile
from api.modules.matching import schemas, service

router = APIRouter(prefix="/me/matches", tags=["matching"])


async def _profile(db: AsyncSession, user: User) -> CandidateProfile:
    """The signed-in candidate's profile, created if they have never had one.

    Not a 404. Profiles are created lazily on first access, so a brand-new user
    who signs in and comes straight here has none -- and 404 sent them to the
    interface's error state instead of the "add your skills" prompt this module
    already returns via `has_skills`. That is the difference between a dead end
    and a next step, and it was reaching every new candidate who did not visit
    their profile page first.

    `ensure_profile` commits when it creates and writes nothing when it does
    not, so `record()` further down these handlers still has no uncommitted work
    to sweep up.
    """
    return await ensure_profile(db, user.id)


def _to_match(scored: service.ScoredJob) -> schemas.MatchOut:
    r = scored.result
    return schemas.MatchOut(
        job=schemas.JobSummary.model_validate(scored.job),
        score=r.score,
        coverage=round(r.coverage, 4),
        matched=[schemas.MatchedSkillOut(**vars(m)) for m in r.matched],
        missing=[
            schemas.MissingSkillOut(
                skill_id=m.skill_id,
                nos_code=m.nos_code,
                name=m.name,
                importance=m.importance,
                is_mandatory=m.is_mandatory,
                nsqf_level=float(m.nsqf_level) if m.nsqf_level is not None else None,
            )
            for m in r.missing
        ],
        missing_mandatory=r.missing_mandatory,
        level_shortfall=float(r.level_shortfall) if r.level_shortfall is not None else None,
        experience_shortfall=r.experience_shortfall,
        capped_by_mandatory=r.capped_by_mandatory,
        locality=scored.locality,
    )


@router.get("", response_model=schemas.MatchPage)
async def list_matches(
    limit: int = Query(20, ge=1, le=50),
    state_id: uuid.UUID | None = Query(
        None, description="Only vacancies in this state. The candidate's choice, never a default."
    ),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_candidate),
) -> schemas.MatchPage:
    profile = await _profile(db, user)
    # `match_jobs` has accepted `state_id` since Sprint 8 and nothing ever
    # passed it. Opt-in only: filtering by where someone lives would hide every
    # vacancy they would move for.
    scored = await service.match_jobs(db, profile.id, limit=limit, state_id=state_id)

    await record(
        db,
        "matches_viewed",
        user_id=user.id,
        payload={"returned": len(scored)},
    )
    return schemas.MatchPage(
        items=[_to_match(s) for s in scored],
        total=len(scored),
        has_skills=bool(await service.has_declared_skills(db, profile.id)),
    )


@router.get("/{slug}", response_model=schemas.MatchDetail)
async def match_detail(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_candidate),
) -> schemas.MatchDetail:
    """One job, scored, with the courses that close its gap."""
    profile = await _profile(db, user)
    scored = await service.match_job_by_slug(db, profile.id, slug)
    if scored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    courses = await service.courses_closing_gap(db, scored.result.missing)
    entry = await service.entry_routes_for_job(db, scored.job.id)

    await record(
        db,
        "match_opened",
        user_id=user.id,
        subject_type="job",
        subject_id=scored.job.id,
        payload={"score": scored.result.score, "missing": len(scored.result.missing)},
    )
    if scored.result.missing:
        await record(
            db,
            "gap_viewed",
            user_id=user.id,
            subject_type="job",
            subject_id=scored.job.id,
            payload={
                "missing": len(scored.result.missing),
                "mandatory": scored.result.missing_mandatory,
            },
        )
    if courses:
        # Subjected to the **course**, not the job. It recorded
        # `subject_type="job"` and a bare count until Sprint 24, so which
        # course was recommended could not be recovered -- and `course_opened`
        # has always written `{"from_job": slug}`, so the join key existed on
        # one side only and ADR-025's click-through has been uncomputable since
        # Sprint 10. `from_job` is spelled exactly as that handler spells it.
        #
        # Rows written before migration 0025 carry this name with
        # `subject_type="job"`. They are not backfilled -- an event is a fact
        # about what happened -- so any query must filter on the subject type.
        await record_many(
            db,
            [
                (
                    "course_recommended",
                    {
                        "user_id": user.id,
                        "subject_type": "course",
                        "subject_id": suggestion.course.id,
                        "payload": {
                            "from_job": scored.job.slug,
                            "closes": suggestion.closes_count,
                            "rank": rank,
                        },
                    },
                )
                for rank, suggestion in enumerate(courses)
            ],
        )

    base = _to_match(scored)
    return schemas.MatchDetail(
        **base.model_dump(),
        courses=[
            schemas.CourseSuggestionOut(
                slug=c.course.slug,
                title=c.course.title,
                mode=c.course.mode,
                duration_hours=c.course.duration_hours,
                fee_inr=c.course.fee_inr,
                closes=c.closes,
                closes_count=c.closes_count,
                gap_size=c.gap_size,
                covers_mandatory=c.covers_mandatory,
            )
            for c in courses
        ],
        entry=(
            schemas.EntryRouteOut(
                qp_code=entry.qp_code,
                qp_name=entry.qp_name,
                routes_total=entry.routes_total,
                education_options=entry.education_options,
                lowest_experience_years=(
                    float(entry.lowest_experience_years)
                    if entry.lowest_experience_years is not None
                    else None
                ),
            )
            if entry
            else None
        ),
    )
