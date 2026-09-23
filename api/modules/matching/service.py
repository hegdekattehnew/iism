"""Loading what the scorer needs, and turning a gap into something actionable.

Two stages, because scoring every candidate against every job does not survive
growth (ADR-007). Retrieval narrows by shared concepts and hard filters; only
the survivors are scored. At 20 jobs the difference is invisible; at 200,000 it
is the difference between a page and a timeout, and retrofitting it later means
rewriting the scorer's callers.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.marketplace.models import (
    CandidatePreferredLocation,
    CandidateProfile,
    CandidateSkill,
    Course,
    CourseSkill,
    Job,
    JobSkill,
    open_job,
)
from api.modules.matching.scoring import (
    HeldSkill,
    MatchResult,
    MissingSkill,
    RequiredSkill,
    score_match,
)
from api.modules.skills.hierarchy import QpEntryRoute, QpSkill, QualificationPack
from api.modules.skills.models import Skill

# How many jobs survive retrieval to be scored. Generous relative to the current
# catalogue and cheap to raise; it exists so the shape is right, not to ration.
RETRIEVAL_LIMIT = 500


@dataclass(frozen=True)
class ScoredJob:
    job: Job
    result: MatchResult
    # 2 same district, 1 same state, 0 elsewhere or unknown. A tie-break, never
    # part of the score -- see `_locality`.
    locality: int = 0


@dataclass(frozen=True)
class CandidateFacts:
    """What matching reads off the profile besides its skills."""

    years_experience: int | None
    states: frozenset[uuid.UUID]
    districts: frozenset[uuid.UUID]


async def candidate_facts(db: AsyncSession, profile_id: uuid.UUID) -> CandidateFacts:
    """Where the candidate lives *and* where they said they would work.

    `CandidatePreferredLocation` had no reader at all before Sprint 23. Where
    someone lives and where they will work are different facts, and either makes
    a vacancy local to them.
    """
    profile = await db.get(CandidateProfile, profile_id)
    preferred = (
        await db.execute(
            select(
                CandidatePreferredLocation.state_id, CandidatePreferredLocation.district_id
            ).where(CandidatePreferredLocation.profile_id == profile_id)
        )
    ).all()
    states = {row.state_id for row in preferred if row.state_id}
    districts = {row.district_id for row in preferred if row.district_id}
    if profile is not None:
        if profile.state_id:
            states.add(profile.state_id)
        if profile.district_id:
            districts.add(profile.district_id)
    return CandidateFacts(
        years_experience=profile.years_experience if profile is not None else None,
        states=frozenset(states),
        districts=frozenset(districts),
    )


def _locality(job: Job, facts: CandidateFacts) -> int:
    """How local a vacancy is to this candidate. Deliberately **not** a score.

    It orders jobs that scored identically and nothing else, so it can never
    hide a vacancy or push a better match below a worse one: "a candidate one
    standard short of a strong match needs telling, not hiding" applies to
    distance too. It stays out of `scoring.py` because that scorer also ranks
    candidates for employers (ADR-037), where a location term would quietly
    rank people by proximity -- a hiring decision this product does not make.
    """
    if job.district_id and job.district_id in facts.districts:
        return 2
    if job.state_id and job.state_id in facts.states:
        return 1
    return 0


@dataclass(frozen=True)
class CourseSuggestion:
    """A course, and what it does about *this* gap specifically."""

    course: Course
    closes: list[str]
    closes_count: int
    gap_size: int
    covers_mandatory: int


@dataclass(frozen=True)
class EntryRouteFit:
    """Whether the candidate can enrol on the qualification behind a job.

    Deliberately not folded into the score. Eligibility is a yes or a no, and
    averaging it into a percentage would hide the one fact that decides whether
    an application is worth making.
    """

    qp_code: str
    qp_name: str
    routes_total: int
    """How many alternative ways in the qualification publishes."""
    education_options: list[str]
    lowest_experience_years: Decimal | None


async def _held_skills(db: AsyncSession, profile_id: uuid.UUID) -> list[HeldSkill]:
    rows = (
        await db.execute(
            select(
                CandidateSkill.skill_id,
                Skill.concept_id,
                Skill.name,
                CandidateSkill.proficiency,
                CandidateSkill.source,
            )
            .join(Skill, Skill.id == CandidateSkill.skill_id)
            .where(CandidateSkill.profile_id == profile_id)
        )
    ).all()
    return [
        HeldSkill(
            skill_id=r.skill_id,
            concept_id=r.concept_id,
            name=r.name,
            proficiency=r.proficiency,
            source=r.source,
        )
        for r in rows
    ]


async def requirements_for(
    db: AsyncSession, job_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[RequiredSkill]]:
    if not job_ids:
        return {}
    rows = (
        await db.execute(
            select(
                JobSkill.job_id,
                JobSkill.skill_id,
                Skill.concept_id,
                Skill.nos_code,
                Skill.name,
                Skill.nsqf_level,
                JobSkill.importance,
                JobSkill.is_mandatory,
            )
            .join(Skill, Skill.id == JobSkill.skill_id)
            .where(JobSkill.job_id.in_(job_ids))
        )
    ).all()
    out: dict[uuid.UUID, list[RequiredSkill]] = {}
    for r in rows:
        out.setdefault(r.job_id, []).append(
            RequiredSkill(
                skill_id=r.skill_id,
                concept_id=r.concept_id,
                nos_code=r.nos_code,
                name=r.name,
                nsqf_level=r.nsqf_level,
                importance=r.importance,
                is_mandatory=r.is_mandatory,
            )
        )
    return out


async def match_jobs(
    db: AsyncSession,
    profile_id: uuid.UUID,
    *,
    limit: int = 20,
    state_id: uuid.UUID | None = None,
) -> list[ScoredJob]:
    """Rank published jobs for one candidate."""
    held = await _held_skills(db, profile_id)
    facts = await candidate_facts(db, profile_id)
    if not held:
        # No declared skills, no defensible ranking. An arbitrary order dressed
        # up as a match would be worse than an empty list with a prompt to add
        # skills, which is what the interface shows.
        return []

    concept_keys = [h.concept_id for h in held if h.concept_id]
    skill_keys = [h.skill_id for h in held]

    # Retrieval: only jobs sharing at least one required standard with the
    # candidate. A job with nothing in common cannot score above zero, so
    # scoring it would be work spent to produce a row nobody sees.
    retrieval = (
        select(Job.id)
        .join(JobSkill, JobSkill.job_id == Job.id)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(open_job())
        .where(Skill.concept_id.in_(concept_keys) | Skill.id.in_(skill_keys))
    )
    if state_id is not None:
        retrieval = retrieval.where(Job.state_id == state_id)
    # Ordered before the cap so which jobs survive it is at least reproducible.
    # Still arbitrary with respect to fit: the real fix is ranking retrieval by
    # shared-standard count, which is out of scope until the catalogue is large
    # enough for the cap to bite. Without the ORDER BY, which 500 survived was
    # Postgres's choice, and could change between two identical requests.
    job_ids = list(
        (await db.scalars(retrieval.distinct().order_by(Job.id).limit(RETRIEVAL_LIMIT))).all()
    )
    if not job_ids:
        return []

    requirements = await requirements_for(db, job_ids)
    jobs = {j.id: j for j in (await db.scalars(select(Job).where(Job.id.in_(job_ids)))).all()}

    scored = [
        ScoredJob(
            job=jobs[job_id],
            result=score_match(
                requirements.get(job_id, []),
                held,
                job_level_min=jobs[job_id].nsqf_level_min,
                candidate_level=attained_level(held, requirements.get(job_id, [])),
                job_min_years=jobs[job_id].experience_min_years,
                candidate_years=facts.years_experience,
            ),
            locality=_locality(jobs[job_id], facts),
        )
        for job_id in job_ids
        if job_id in jobs
    ]
    # Score, then coverage, then locality, then title: a stable order, so the
    # same inputs always produce the same page. Locality only breaks ties.
    scored.sort(key=lambda s: (-s.result.score, -s.result.coverage, -s.locality, s.job.title))
    return scored[:limit]


def attained_level(held: list[HeldSkill], required: list[RequiredSkill]) -> Decimal | None:
    """The level of the standards the candidate actually holds for this job.

    Not the candidate's highest level anywhere: holding one level-6 standard
    does not make someone a level-6 match for a job built from level-3 units.
    """
    keys = {h.concept_id or h.skill_id for h in held}
    levels = [
        r.nsqf_level
        for r in required
        if r.nsqf_level is not None and (r.concept_id or r.skill_id) in keys
    ]
    return max(levels) if levels else None


async def courses_closing_gap(
    db: AsyncSession, missing: list[MissingSkill], *, limit: int = 5
) -> list[CourseSuggestion]:
    """Rank courses by how much of *this* gap they close.

    Not by how good the course is in general -- by how much of what this person
    is missing it covers. A course teaching nine things they already have and
    one they need is worth less than a course teaching only the one.
    """
    if not missing:
        return []

    concept_keys = [m.concept_id for m in missing if m.concept_id]
    skill_keys = [m.skill_id for m in missing]
    mandatory_keys = {m.concept_id or m.skill_id for m in missing if m.is_mandatory}
    wanted = {m.concept_id or m.skill_id: m for m in missing}

    rows = (
        await db.execute(
            select(CourseSkill.course_id, Skill.concept_id, Skill.id, Skill.name)
            .join(Skill, Skill.id == CourseSkill.skill_id)
            .join(Course, Course.id == CourseSkill.course_id)
            .where(Course.status == "published")
            .where(Skill.concept_id.in_(concept_keys) | Skill.id.in_(skill_keys))
        )
    ).all()
    if not rows:
        return []

    covered: dict[uuid.UUID, dict[uuid.UUID, str]] = {}
    for r in rows:
        key = r.concept_id or r.id
        if key in wanted:
            covered.setdefault(r.course_id, {})[key] = r.name

    courses = {
        c.id: c
        for c in (await db.scalars(select(Course).where(Course.id.in_(list(covered.keys()))))).all()
    }

    suggestions = [
        CourseSuggestion(
            course=courses[course_id],
            closes=sorted(names.values()),
            closes_count=len(names),
            gap_size=len(missing),
            covers_mandatory=len(set(names.keys()) & mandatory_keys),
        )
        for course_id, names in covered.items()
        if course_id in courses
    ]
    # Mandatory coverage first: a course that unblocks an application beats one
    # that merely improves a score.
    suggestions.sort(key=lambda s: (-s.covers_mandatory, -s.closes_count, s.course.title))
    return suggestions[:limit]


async def entry_routes_for_job(db: AsyncSession, job_id: uuid.UUID) -> EntryRouteFit | None:
    """The qualification behind a job, and the ways in to it.

    Derived rather than declared. `Job` has no qualification field and nothing
    populates the one on `Course`, but a job's required standards do belong to
    qualifications -- so the qualification covering most of what the job asks
    for is the one it is really hiring against. That is a claim the data
    supports, where a hand-entered code would be a claim nobody maintained.
    """
    required = (await db.scalars(select(JobSkill.skill_id).where(JobSkill.job_id == job_id))).all()
    if not required:
        return None

    # The qualification containing the most of this job's standards. Ties break
    # on the lower level: the easiest route in is the useful answer.
    best = (
        await db.execute(
            select(
                QpSkill.qp_id,
                func.count().label("covered"),
            )
            .join(QualificationPack, QualificationPack.id == QpSkill.qp_id)
            .where(QpSkill.skill_id.in_(list(required)))
            .where(QualificationPack.is_current.is_(True))
            .group_by(QpSkill.qp_id)
            .order_by(func.count().desc())
            .limit(1)
        )
    ).first()
    if best is None:
        return None

    qp = await db.get(QualificationPack, best.qp_id)
    if qp is None:  # pragma: no cover - just selected
        return None

    routes = (
        await db.execute(
            select(QpEntryRoute.education_desc, QpEntryRoute.experience_years).where(
                QpEntryRoute.qp_id == qp.id
            )
        )
    ).all()
    if not routes:
        return None

    years = [r.experience_years for r in routes if r.experience_years is not None]
    return EntryRouteFit(
        qp_code=qp.qp_code,
        qp_name=qp.name,
        routes_total=len(routes),
        education_options=sorted({r.education_desc for r in routes if r.education_desc}),
        # The easiest way in is what a candidate needs to know.
        lowest_experience_years=min(years) if years else None,
    )


async def has_declared_skills(db: AsyncSession, profile_id: uuid.UUID) -> bool:
    """Zero declared skills is a different state from zero matches.

    The interface says "add your skills" rather than "no matches found", which
    is the difference between a dead end and a next step.
    """
    return bool(
        await db.scalar(
            select(func.count())
            .select_from(CandidateSkill)
            .where(CandidateSkill.profile_id == profile_id)
        )
    )


async def match_job_by_slug(db: AsyncSession, profile_id: uuid.UUID, slug: str) -> ScoredJob | None:
    """Score one named job, whether or not it would survive retrieval.

    A candidate who follows a link to a job sharing nothing with their profile
    should see an honest zero and the full gap, not a 404.
    """
    # `open_job()`: a closed vacancy must not keep producing a gap
    # analysis and a course plan for a job nobody can apply to.
    job = await db.scalar(select(Job).where(Job.slug == slug, open_job()))
    if job is None:
        return None
    held = await _held_skills(db, profile_id)
    facts = await candidate_facts(db, profile_id)
    requirements = (await requirements_for(db, [job.id])).get(job.id, [])
    return ScoredJob(
        job=job,
        result=score_match(
            requirements,
            held,
            job_level_min=job.nsqf_level_min,
            candidate_level=attained_level(held, requirements),
            job_min_years=job.experience_min_years,
            candidate_years=facts.years_experience,
        ),
        locality=_locality(job, facts),
    )
