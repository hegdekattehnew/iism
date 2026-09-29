"""BL-3.1: turn one vendor's webhook payload into a written `CandidateSkill`.

**No new table, and nothing new persisted beyond the existing
`CandidateSkill` row.** ADR-023 names "assessment results" among the data
that must go through an encryption path before it is collected, and that
path does not exist yet (`projectContextForMe.md` §13.4). This module
deliberately never crosses that line: it persists only a coarse pass/fail
against a named standard, through the same `CandidateSkill.source` column
the platform already stores in plaintext for self-declared skills -- not a
score, a transcript, or free-text feedback, any of which would be a genuine
"assessment result" and would need that path built first. The webhook
answers synchronously with what happened instead of writing an audit trail
-- which is also what a real integration partner needs: a definite
success/failure, not an async log to poll.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.assessment import AssessmentProvider, get_assessment_provider
from api.core.redaction import mask_phone
from api.modules.identity import User, normalise_phone
from api.modules.marketplace import get_or_create_profile, record_verified_skill
from api.modules.skills import get_skill_by_nos_code

log = structlog.get_logger("iism.assessment")


class UnknownCandidate(Exception):
    """No account holds this phone number, or it holds no candidate profile."""


class UnknownStandard(Exception):
    """No skill in the corpus carries this NOS/QP code."""


async def ingest_result(
    db: AsyncSession, payload: dict, *, provider: AssessmentProvider | None = None
) -> tuple[int, int]:
    """Returns `(added, updated)` from `record_verified_skill`. Raises
    `UnknownCandidate`/`UnknownStandard` for the route to turn into a 404 --
    a provider needs to know a result did not land, and why, not a silent 200.
    """
    result = (provider or get_assessment_provider()).parse_result(payload)
    phone = normalise_phone(result.phone)

    user = await db.scalar(select(User).where(User.phone == phone))
    if user is None:
        log.warning("assessment.unknown_candidate", standard_code=result.standard_code)
        raise UnknownCandidate(mask_phone(phone))
    # Lazy, like every other first touch of a profile (`/me/matches`,
    # `add_skill`): an account that has never opened its profile still holds
    # a real result.
    profile = await get_or_create_profile(db, user.id)

    skill = await get_skill_by_nos_code(db, result.standard_code)
    if skill is None:
        log.warning("assessment.unknown_standard", standard_code=result.standard_code)
        raise UnknownStandard(result.standard_code)

    if not result.passed:
        # A failed attempt is not evidence of anything -- it neither adds nor
        # upgrades a skill, and it is not an error either.
        return 0, 0

    return await record_verified_skill(db, profile, skill.slug, source="assessed")
