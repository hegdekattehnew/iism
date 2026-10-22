"""An organisation's training centres (Sprint 95, ADR-102).

Every route names the **organisation** in the path and the centre under it. Access to a centre is
inherited from the organisation's membership (`core.authorization.centre_for`), so a centre has no
membership of its own and a stranger to the organisation, or an organisation reaching another's
centre, gets the same 404 as for a slug that does not exist (ADR-038).

`/centres/bulk/*` is declared before `/centres/{centre_slug}`, or `bulk` is captured as a slug.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, centre_for, require
from api.core.database import get_db_session
from api.modules.centres import bulk, service
from api.modules.centres.schemas import (
    CentreBulkReportOut,
    CentreBulkRowOut,
    CentreIn,
    CentreList,
    CentreOut,
)

router = APIRouter(prefix="/org/{org_slug}/centres", tags=["centres"])

CanReadCentres = Depends(require(Permission.CENTRE_READ, "centre"))
CanManageCentres = Depends(require(Permission.CENTRE_MANAGE, "centre"))

_CSV_BODY: dict[str, object] = {
    "requestBody": {
        "required": True,
        "content": {"text/csv": {"schema": {"type": "string"}}},
    }
}


@router.get("", response_model=CentreList)
async def list_centres(
    context: TenantContext = CanReadCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreList:
    centres = await service.centres_of(db, context.tenant)
    return CentreList(
        items=[service.out(c) for c in centres],
        total=len(centres),
        active=sum(1 for c in centres if c.closed_at is None),
        limit=service.MAX_CENTRES,
    )


@router.post("", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
async def create_centre(
    payload: CentreIn,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreOut:
    centre = await service.create_centre(db, context.tenant, context.user, payload)
    return service.out(centre)


@router.get("/bulk/template")
async def centres_template(context: TenantContext = CanManageCentres) -> Response:
    return Response(
        bulk.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": 'attachment; filename="centres-template.csv"'},
    )


def _report(report: bulk.Report) -> CentreBulkReportOut:
    return CentreBulkReportOut(
        applied=report.applied,
        rows=[
            CentreBulkRowOut(
                row=r.row,
                status=r.status,
                name=r.name,
                messages=r.messages,
                slug=r.slug,
                created=r.created,
            )
            for r in report.rows
        ],
        notes=report.notes,
        ok=report.count("ok"),
        warnings=report.count("warning"),
        errors=report.count("error"),
        skipped=report.count("skip"),
        created=report.created,
        remaining=report.remaining,
        errors_csv=report.errors_csv,
    )


async def _file(
    request: Request, db: AsyncSession, context: TenantContext, *, apply: bool
) -> CentreBulkReportOut:
    try:
        text = bulk.decode(await request.body())
        report = await bulk.run(db, context.tenant, text, apply=apply, actor_id=context.user.id)
    except bulk.BulkFileError as error:
        raise HTTPException(error.status_code, error.message) from error
    return _report(report)


@router.post("/bulk/check", response_model=CentreBulkReportOut, openapi_extra=_CSV_BODY)
async def check_centres(
    request: Request,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreBulkReportOut:
    """Validate every row and say what an apply would do. Writes nothing."""
    return await _file(request, db, context, apply=False)


@router.post("/bulk/apply", response_model=CentreBulkReportOut, openapi_extra=_CSV_BODY)
async def apply_centres(
    request: Request,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreBulkReportOut:
    return await _file(request, db, context, apply=True)


@router.get("/{centre_slug}", response_model=CentreOut)
async def get_centre(
    centre_slug: str,
    context: TenantContext = CanReadCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreOut:
    return service.out(await centre_for(db, context, centre_slug))


@router.put("/{centre_slug}", response_model=CentreOut)
async def update_centre(
    centre_slug: str,
    payload: CentreIn,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreOut:
    centre = await centre_for(db, context, centre_slug)
    updated = await service.update_centre(db, context.tenant, centre, context.user, payload)
    return service.out(updated)


@router.post("/{centre_slug}/close", response_model=CentreOut)
async def close_centre(
    centre_slug: str,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreOut:
    centre = await centre_for(db, context, centre_slug)
    closed = await service.close_centre(db, context.tenant, centre, context.user)
    return service.out(closed)


@router.post("/{centre_slug}/reopen", response_model=CentreOut)
async def reopen_centre(
    centre_slug: str,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> CentreOut:
    centre = await centre_for(db, context, centre_slug)
    return service.out(await service.reopen_centre(db, centre))
