"""The assessment provider's one endpoint (Sprint 35, BL-3.1).

Sibling of `marketplace/partner_routes.py`'s external-system pattern: an
API key, not a `User` (`core.security.get_service_account`), but this one
writes rather than reads, so it asks for the `assessment:write` scope
specifically rather than the default `read`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.assessment import AssessmentError
from api.core.database import get_db_session
from api.core.security import require_service_scope
from api.modules.assessment import schemas, service
from api.modules.identity.models import ServiceAccount

router = APIRouter(prefix="/partners/assessment-results", tags=["partners"])
RequiresAssessmentWrite = Depends(require_service_scope("assessment:write"))


@router.post("", response_model=schemas.AssessmentWebhookOut)
async def submit_assessment_result(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    # Unused beyond authenticating and scoping the call -- see
    # `partner_routes.py`'s identical note on its own `account` parameter.
    account: ServiceAccount = RequiresAssessmentWrite,
) -> schemas.AssessmentWebhookOut:
    try:
        added, updated = await service.ingest_result(db, payload)
    except AssessmentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except service.UnknownCandidate as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No candidate found for phone {exc}"
        ) from exc
    except service.UnknownStandard as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown standard: {exc}") from exc
    return schemas.AssessmentWebhookOut(
        written=bool(added or updated), added=added, updated=updated
    )
