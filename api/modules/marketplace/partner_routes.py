"""The external-system actor's one endpoint (Sprint 33, BL-7.2).

A new route rather than `GET /jobs` behind a second, optional guard: `/jobs`
is already public, so gating it would protect nothing and prove nothing in a
demo. This exists to make the auth mechanism demonstrably do something --
`with a key` and `without one` give different answers.

Same data, same `service.list_jobs`, same `JobOut` shape the public listing
already returns: a partner is not a candidate or an employer, but it is not
owed a *different* answer either, and a second query path here would be the
kind of duplicated rule this codebase's own conventions warn against.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.core.security import get_service_account
from api.modules.identity.models import ServiceAccount
from api.modules.marketplace import schemas, service

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("/jobs", response_model=schemas.JobPage)
async def partner_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
    account: ServiceAccount = Depends(get_service_account),
) -> schemas.JobPage:
    """Open vacancies, for a partner holding a valid API key.

    `account` is unused beyond authenticating the call — there is no
    per-partner filter yet (`SERVICE_ACCOUNT_SCOPES` is a set of one), so
    naming it in the signature is what makes the dependency run, not a value
    this handler reads.
    """
    items, total = await service.list_jobs(db, limit=limit, offset=offset)
    overrides = await overrides_for(db, "job", items, ("title", "description"), locale)
    return schemas.JobPage(
        items=[
            schemas.JobOut.model_validate(j).model_copy(update=overrides.get(j.id, {}))
            for j in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
