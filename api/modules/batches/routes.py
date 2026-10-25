"""Batches (Sprint 98, ADR-103).

Every route hangs off the **acting organisation's** slug, where `require()` has resolved the
membership and answers a stranger with 404 (ADR-038). The acting tenant is either a delivering
organisation (it reaches every batch of every one of its centres) or a centre (its own manager
reaches only that centre's batches); the service applies that scope, so a batch of another
organisation is the same 404 as one that does not exist.

The literal paths are declared before `/{batch_id}`.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.batches import bulk, learners, service
from api.modules.batches.schemas import (
    BatchBulkPublishIn,
    BatchBulkPublishOut,
    BatchBulkPublishRowOut,
    BatchBulkReportOut,
    BatchBulkRowOut,
    BatchIn,
    BatchLearnersOut,
    BatchList,
    BatchOut,
    BatchOverview,
    BatchUpdateIn,
    CentreStatusIn,
    CourseBatchesOut,
    DeliverableCourses,
)

router = APIRouter(prefix="/org/{org_slug}/batches", tags=["batches"])

CanReadBatches = Depends(require(Permission.BATCH_READ, "batch"))
CanManageBatches = Depends(require(Permission.BATCH_MANAGE, "batch"))
# The learners of a batch, their contact included: the centre and its organisation's owners and
# admins (ADR-103, decision 1). A plain member reads the batches and never a person.
CanSeeLearners = Depends(require(Permission.BATCH_LEARNERS, "batch"))
# A file of batches names a centre on every row, so it is the organisation's: `CENTRE_MANAGE` is an
# admin's and an owner's and is held by no centre manager, and a centre has no "centre" capability.
CanUploadBatches = Depends(require(Permission.CENTRE_MANAGE, "centre"))
# The seller's own view of how its courses are being run (counts only).
CanSeeBatchesOfMyCourses = Depends(require(Permission.DELIVERY_READ, "course"))

_CSV_BODY: dict[str, object] = {
    "requestBody": {
        "required": True,
        "content": {"text/csv": {"schema": {"type": "string"}}},
    }
}


@router.get("", response_model=BatchList)
async def list_batches(
    phase: Literal["draft", "open", "full", "running", "finished", "cancelled"] | None = None,
    centre: str | None = Query(default=None, max_length=200),
    course: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=25, ge=1, le=service.PAGE_MAX),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = CanReadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchList:
    return await service.list_batches(
        db,
        context.tenant,
        phase=phase,
        centre_slug=centre,
        course_slug=course,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
async def create_batch(
    payload: BatchIn,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.create_batch(db, context.tenant, context.user, payload)


@router.get("/courses", response_model=DeliverableCourses)
async def deliverable_courses(
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> DeliverableCourses:
    """The courses a batch can be made of: this organisation's own, and those it is authorised to
    deliver. **Planning's, not reading's**: it names other organisations' arrangements, which a
    centre's manager (who reads their centre's batches) has no part in."""
    return await service.deliverable_courses(db, context.tenant)


@router.get("/overview", response_model=BatchOverview)
async def batches_overview(
    context: TenantContext = CanReadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOverview:
    """What to look at today: drafts, what starts this week, what is running, seats still free in
    classes about to begin, and the next few to start."""
    return await service.overview(db, context.tenant)


@router.get("/of-my-courses", response_model=CourseBatchesOut)
async def batches_of_my_courses(
    context: TenantContext = CanSeeBatchesOfMyCourses,
    db: AsyncSession = Depends(get_db_session),
) -> CourseBatchesOut:
    """How other organisations run this seller's courses: per course and organisation, counts of
    published batches by phase and seats. No learner, no contact, no centre."""
    return await service.of_my_courses(db, context.tenant)


@router.get("/bulk/template")
async def batches_template(context: TenantContext = CanUploadBatches) -> Response:
    return Response(
        bulk.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": 'attachment; filename="batches-template.csv"'},
    )


def _report(report: bulk.Report) -> BatchBulkReportOut:
    return BatchBulkReportOut(
        applied=report.applied,
        rows=[
            BatchBulkRowOut(
                row=r.row,
                status=r.status,
                course=r.course,
                centre=r.centre,
                messages=r.messages,
                id=r.id,
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
        errors_csv=report.errors_csv,
    )


async def _file(
    request: Request, db: AsyncSession, context: TenantContext, *, apply: bool
) -> BatchBulkReportOut:
    try:
        text = bulk.decode(await request.body())
        report = await bulk.run(db, context.tenant, text, apply=apply, actor=context.user)
    except bulk.BulkFileError as error:
        raise HTTPException(error.status_code, error.message) from error
    return _report(report)


@router.post("/bulk/check", response_model=BatchBulkReportOut, openapi_extra=_CSV_BODY)
async def check_batches(
    request: Request,
    context: TenantContext = CanUploadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchBulkReportOut:
    """Validate every row and say what an apply would do. Writes nothing."""
    return await _file(request, db, context, apply=False)


@router.post("/bulk/apply", response_model=BatchBulkReportOut, openapi_extra=_CSV_BODY)
async def apply_batches(
    request: Request,
    context: TenantContext = CanUploadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchBulkReportOut:
    """Check the file again, then create each valid row as a **draft**. Never publishes."""
    return await _file(request, db, context, apply=True)


@router.post("/bulk/publish", response_model=BatchBulkPublishOut)
async def publish_batches(
    payload: BatchBulkPublishIn,
    context: TenantContext = CanUploadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchBulkPublishOut:
    results = await bulk.publish_many(db, context.tenant, context.user, payload.ids)
    return BatchBulkPublishOut(
        results=[
            BatchBulkPublishRowOut(id=r.id, published=r.published, message=r.message)
            for r in results
        ],
        published=sum(1 for r in results if r.published),
        refused=sum(1 for r in results if not r.published),
    )


@router.get("/{batch_id}", response_model=BatchOut)
async def get_batch(
    batch_id: uuid.UUID,
    context: TenantContext = CanReadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.get_batch(db, context.tenant, batch_id)


@router.put("/{batch_id}", response_model=BatchOut)
async def update_batch(
    batch_id: uuid.UUID,
    payload: BatchUpdateIn,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.update_batch(db, context.tenant, batch_id, payload)


@router.post("/{batch_id}/publish", response_model=BatchOut)
async def publish_batch(
    batch_id: uuid.UUID,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.publish_batch(db, context.tenant, context.user, batch_id)


@router.post("/{batch_id}/cancel", response_model=BatchOut)
async def cancel_batch(
    batch_id: uuid.UUID,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.cancel_batch(db, context.tenant, context.user, batch_id)


@router.get("/{batch_id}/learners", response_model=BatchLearnersOut)
async def batch_learners(
    batch_id: uuid.UUID,
    context: TenantContext = CanSeeLearners,
    db: AsyncSession = Depends(get_db_session),
) -> BatchLearnersOut:
    """Who registered interest in this batch, the longest-waiting unanswered first, with the contact
    they chose to share (gone once they withdraw)."""
    return await learners.learners_of(db, context.tenant, batch_id)


@router.patch("/{batch_id}/learners/{interest_id}", response_model=BatchLearnersOut)
async def set_learner_status(
    batch_id: uuid.UUID,
    interest_id: uuid.UUID,
    payload: CentreStatusIn,
    context: TenantContext = CanSeeLearners,
    db: AsyncSession = Depends(get_db_session),
) -> BatchLearnersOut:
    """Mark a learner contacted, enrolled (takes a seat) or attended (after it started)."""
    return await learners.set_status(
        db, context.tenant, context.user, batch_id, interest_id, payload.status
    )
