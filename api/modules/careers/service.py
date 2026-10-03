"""Where could this person move to next, and what would it take (ADR-049).

A composition, not a calculation. The taxonomy fact -- which roles build on one
-- is `skills.roles_above`; the person's fit is `matching.score_against_roles`,
which is the one scorer (ADR-037); the courses are `matching.courses_closing_gap`.
This module resolves *where the person starts*, puts those three together, and
measures that somebody looked.

Computed at view time and never stored, like the rejected-application gap: the
panel shrinks as the person closes it, and nothing here becomes a claim about a
person that could go stale. Nothing is written, so erasure has nothing to remove.
"""

import uuid
from dataclasses import dataclass
from typing import Literal

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.marketplace.models import (
    CandidateExperience,
    CandidatePreferredRole,
    CandidateSkill,
)
from api.modules.matching import (
    CourseSuggestion,
    RoleFit,
    courses_closing_gap,
    score_against_roles,
)
from api.modules.skills import RoleLadder, RoleStepUp, roles_above, search_roles

log = structlog.get_logger("iism.careers")

# Courses shown per step. The match page shows five for one vacancy; a ladder
# shows up to eight steps, so each gets fewer or the page is a catalogue.
COURSES_PER_STEP = 3

AnchorSource = Literal["chosen", "guessed", "none"]


@dataclass(frozen=True)
class CareerStep:
    step: RoleStepUp
    fit: RoleFit
    courses: list[CourseSuggestion]


@dataclass(frozen=True)
class CareerLadder:
    ladder: RoleLadder | None
    """`None` only when there is no starting role to show a ladder from."""
    source: AnchorSource
    has_skills: bool
    steps: list[CareerStep]

    @property
    def needs_choice(self) -> bool:
        return self.ladder is None


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


async def _titles_to_try(db: AsyncSession, profile_id: uuid.UUID) -> list[str]:
    """What the person has said they are, best evidence first: where they work
    now (newest first), then the roles they said they are aiming for."""
    current = (
        await db.scalars(
            select(CandidateExperience.role_title)
            .where(CandidateExperience.profile_id == profile_id, CandidateExperience.is_current)
            .order_by(CandidateExperience.started_on.desc(), CandidateExperience.role_title)
        )
    ).all()
    preferred = (
        await db.scalars(
            select(CandidatePreferredRole.title)
            .where(CandidatePreferredRole.profile_id == profile_id)
            .order_by(CandidatePreferredRole.title)
        )
    ).all()
    return [*current, *preferred]


async def _guess_anchor(db: AsyncSession, profile_id: uuid.UUID) -> RoleLadder | None:
    """Resolve what somebody wrote to a qualification, or admit it cannot.

    **Exact or alias only.** Free text becomes a role through the same search
    everybody else uses, and a hit is trusted only when it is the person's own
    words -- the title exactly, or an alias that *is* the title. A prefix, a
    substring or a fuzzy match is a guess about a guess, and a career ladder
    started from the wrong role is worse than asking: every step after it is
    about somebody else.
    """
    for title in await _titles_to_try(db, profile_id):
        wanted = _norm(title)
        for hit in await search_roles(db, title, limit=3):
            exact = hit.match_kind == "exact" and _norm(hit.job_role) == wanted
            alias = hit.match_kind == "alias" and _norm(hit.matched_on) == wanted
            if not (exact or alias):
                continue
            ladder = await roles_above(db, hit.slug)
            if ladder is not None:
                return ladder
    return None


async def career_ladder(
    db: AsyncSession,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    role_slug: str | None,
) -> CareerLadder:
    """The roles that build on the person's, with their fit for each.

    `role_slug` is the person's own choice and wins. Without one the service
    guesses once, from their profile, and says it guessed. An unknown role is a
    404; a role with no step above it is an empty list -- different answers,
    because "our data shows no further step from here" is something the page can
    say and "that role does not exist" is not.
    """
    source: AnchorSource
    if role_slug is not None:
        ladder = await roles_above(db, role_slug)
        if ladder is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
        source = "chosen"
    else:
        ladder = await _guess_anchor(db, profile_id)
        source = "guessed" if ladder is not None else "none"

    has_skills = (
        await db.scalar(
            select(CandidateSkill.id).where(CandidateSkill.profile_id == profile_id).limit(1)
        )
    ) is not None
    if ladder is None:
        return CareerLadder(ladder=None, source=source, has_skills=has_skills, steps=[])

    fits = await score_against_roles(db, profile_id, [s.qp_id for s in ladder.steps])
    steps = [
        CareerStep(
            step=step,
            fit=fits[step.qp_id],
            courses=await courses_closing_gap(
                db, fits[step.qp_id].result.missing, limit=COURSES_PER_STEP
            ),
        )
        for step in ladder.steps
        if step.qp_id in fits
    ]

    # After every read, outside any pending write (`record()` commits). Subject to
    # the role the ladder started from, never the person; counts only.
    await record(
        db,
        "career_ladder_viewed",
        user_id=user_id,
        subject_type="qualification",
        subject_id=ladder.anchor.qp_id,
        payload={"steps": len(steps), "guessed": source == "guessed"},
    )
    return CareerLadder(ladder=ladder, source=source, has_skills=has_skills, steps=steps)
