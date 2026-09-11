"""Dependencies for routes that act on a *kind* of person, not just any account.

`get_current_user` answers "is someone signed in". It says nothing about which
roles that someone holds, and candidate routes were using it alone -- so an
organisation-only account that opened `/profile` had a `CandidateProfile`
**created and committed** for it by `ensure_profile`, and was then walked through
the candidate onboarding wizard. A signed-in surface must branch on membership,
never on "signed in" alone.
"""

import structlog
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity.models import User
from api.modules.identity.service import has_personal_membership

log = structlog.get_logger("iism.authz")


async def get_current_candidate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """The signed-in user, provided they ever signed up to look for work.

    `ensure_profile` stays lazy -- Sprint 10 depends on a first visit to
    `/me/matches` creating the profile -- but laziness is for candidates who
    have not got round to it yet, not for accounts that never asked to be one.
    A candidate profile is opted into by signing up as a job seeker.

    403, not 404: this is the caller's own account, so nothing about anyone
    else's existence is being disclosed.
    """
    if not await has_personal_membership(db, user.id):
        log.info("authz.not_a_candidate")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has no job-seeker profile")
    return user
