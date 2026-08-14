import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.permissions import require_tenant_role_or_platform_staff
from app.core.security import get_service_account
from app.modules.identity import candidates_service
from app.modules.identity.models import ServiceAccount, User
from app.modules.identity.schemas import BulkUploadResult, ExternalCandidateIntakeRequest

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/bulk-upload", response_model=BulkUploadResult)
async def bulk_upload_candidates(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_tenant_role_or_platform_staff("owner", "admin")),
) -> BulkUploadResult:
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    if (
        reader.fieldnames is None
        or "email" not in reader.fieldnames
        or "full_name" not in reader.fieldnames
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "CSV must have 'email' and 'full_name' columns"
        )
    records = [(row.get("email") or "", row.get("full_name") or "") for row in reader]
    return await candidates_service.bulk_create_candidates(db, records)


@router.post("/external", response_model=BulkUploadResult)
async def external_candidate_intake(
    data: ExternalCandidateIntakeRequest,
    db: AsyncSession = Depends(get_db_session),
    _: ServiceAccount = Depends(get_service_account),
) -> BulkUploadResult:
    records = [(candidate.email, candidate.full_name) for candidate in data.candidates]
    return await candidates_service.bulk_create_candidates(db, records)
