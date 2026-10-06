"""Corpus-wide figures for the landing page.

The homepage used to say what the product does; it should also show what it
holds, and (Sprint 50.5) what has been *done* on it. Every number here is counted
live from the database rather than written into a template, because a marketing
figure that drifts from reality is worse than no figure -- and these are
impressive enough without embellishment.

**One statement, one round trip.** Every count is a scalar subquery in a single
`SELECT`: it backs a page a first-time visitor sees, so it must be cheap, and
the page renders without it if the API is unreachable. Deliberately **not cached**:
a cached count is the "I added a job and the number did not move" bug, and a
person who has just applied or signed up expects the same.

**Where a broad and a narrow figure differ, both are returned and the page names the
narrow one underneath**, the pattern `jobs_posted` / `jobs_open` set. Each figure's
definition is written where it is computed, because a count is a claim.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import ORGANISATION_TYPES  # noqa: F401  (named in the docstrings)
from api.core.config import get_settings
from api.modules.geography.models import District, State
from api.modules.identity.models import Tenant
from api.modules.marketplace.models import (
    CandidateProfile,
    Course,
    Job,
    open_job,
    posted_job,
    skilled_profile,
)
from api.modules.skills.content import PerformanceCriterion
from api.modules.skills.hierarchy import AwardingBody, QpEntryRoute, QualificationPack, Sector
from api.modules.skills.models import Skill


@dataclass(frozen=True)
class CorpusStats:
    standards: int
    qualifications: int
    criteria: int
    awarding_bodies: int
    sectors: int
    states: int
    districts: int
    entry_routes: int
    jobs_posted: int
    jobs_open: int
    courses: int
    # --- who is here and what they have done (Sprint 50.5)
    job_seekers: int
    profiles: int
    employers: int
    employers_hiring: int
    providers: int
    providers_with_course: int
    applications: int
    hires: int
    districts_with_vacancy: int
    # True for anything that is not production's own data: the page then says so.
    demo: bool


def is_demonstration() -> bool:
    """Whether these figures describe a demonstration rather than real use.

    Everything but `ENVIRONMENT=production` is one, and so is any database whose name ends
    `_scale` (the benchmark harness's, whose 50,000 candidates are synthetic and must never
    read as traction). The owner chose to always show the true count, however small; this is
    what stops a seeded database passing for a customer base.
    """
    settings = get_settings()
    database = make_url(settings.database_url).database or ""
    return settings.environment != "production" or database.endswith("_scale")


async def corpus_stats(db: AsyncSession) -> CorpusStats:
    # Imported here, not at module scope: `applications.models` imports this package's models,
    # and `marketplace/__init__` imports this module, so the module-level form is a cycle.
    from api.modules.applications.models import FILLED_STATUSES, Application

    def n(model: Any, *where: Any) -> Any:
        return select(func.count()).select_from(model).where(*where).scalar_subquery()

    def distinct(column: Any, *where: Any) -> Any:
        return select(func.count(func.distinct(column))).where(*where).scalar_subquery()

    row = (
        await db.execute(
            select(
                # **Every number here names rows a visitor can reach.** Retired
                # standards are excluded exactly as they are from search and browse;
                # `posted_job()` includes closed vacancies because each one still has
                # a page, while `open_job()` is the narrower set that browse lists.
                # The homepage shows both and says which is which.
                n(Skill, Skill.source == "nsqf").label("standards"),
                n(QualificationPack, QualificationPack.is_current.is_(True)).label(
                    "qualifications"
                ),
                n(PerformanceCriterion).label("criteria"),
                n(AwardingBody).label("awarding_bodies"),
                n(Sector).label("sectors"),
                # The geography *master list*, not places with activity: what the data
                # can place a vacancy in. `districts_with_vacancy` is the reach.
                n(State).label("states"),
                n(District).label("districts"),
                n(QpEntryRoute).label("entry_routes"),
                n(Job, posted_job()).label("jobs_posted"),
                n(Job, open_job()).label("jobs_open"),
                n(Course, Course.status == "published").label("courses"),
                # **A job seeker is a profile that has declared a standard**
                # (`skilled_profile`, shared with the employer console). `profiles` is every
                # profile row, including the empty ones a visit creates, and is the "signed up"
                # figure shown underneath when it is larger.
                n(CandidateProfile, skilled_profile()).label("job_seekers"),
                n(CandidateProfile).label("profiles"),
                # Organisations, personal workspaces excluded (`ORGANISATION_TYPES`: every
                # candidate owns one, and they are not businesses). "Hiring" means an open
                # vacancy; "with a course" means a published one.
                n(Tenant, Tenant.tenant_type == "employer").label("employers"),
                distinct(Job.tenant_id, open_job()).label("employers_hiring"),
                n(Tenant, Tenant.tenant_type == "course_provider").label("providers"),
                distinct(Course.tenant_id, Course.status == "published").label(
                    "providers_with_course"
                ),
                # Every application made, withdrawn ones included: the candidate did apply.
                n(Application).label("applications"),
                # A hire is `hired` or `completed`. A `no_show` was hired but left the seat
                # empty, which is not a hire to count; a person hired twice counts twice, so
                # the page says "hires", never "people hired".
                n(Application, Application.status.in_(FILLED_STATUSES)).label("hires"),
                # Places, never people in a place, so ADR-057's small-cell rule is not engaged.
                distinct(Job.district_id, open_job()).label("districts_with_vacancy"),
            )
        )
    ).one()
    return CorpusStats(**{k: int(v or 0) for k, v in row._mapping.items()}, demo=is_demonstration())
