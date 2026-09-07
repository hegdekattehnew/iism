"""Corpus-wide figures for the landing page.

The homepage used to say what the product does; it should also show what it
holds. Every number here is counted live from the database rather than written
into a template, because a marketing figure that drifts from reality is worse
than no figure -- and these are impressive enough without embellishment.

One query, ten counts. It backs a page a first-time visitor sees, so it must be
cheap: all of these are index-only or small-table counts, and the page renders
without them if the API is unreachable.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.geography.models import District, State
from api.modules.marketplace.models import Course, Job
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
    jobs: int
    courses: int


async def corpus_stats(db: AsyncSession) -> CorpusStats:
    async def count(model: Any, *where: Any) -> int:
        return (await db.scalar(select(func.count()).select_from(model).where(*where))) or 0

    return CorpusStats(
        # Retired rows are excluded, exactly as they are from search and browse:
        # the number on the homepage must be the number a visitor can then find.
        standards=await count(Skill, Skill.source == "nsqf"),
        qualifications=await count(QualificationPack, QualificationPack.is_current.is_(True)),
        criteria=await count(PerformanceCriterion),
        awarding_bodies=await count(AwardingBody),
        sectors=await count(Sector),
        states=await count(State),
        districts=await count(District),
        entry_routes=await count(QpEntryRoute),
        jobs=await count(Job, Job.status == "published"),
        courses=await count(Course, Course.status == "published"),
    )
