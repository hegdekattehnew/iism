"""Bulk upload of vacancies and courses (Sprint 51, ADR-063).

Three steps per kind, each named by the organisation in the path and granted by the caller's
membership (ADR-039): `check` (writes nothing), `apply` (creates drafts) and `publish` (the
explicit second act). The body of `check` and `apply` is the file itself, sent as `text/csv`: no
multipart, no new dependency, and the browser reads the file with `file.text()`.

**Declared before `publishing_router`.** `POST /org/{slug}/jobs/{slug}/publish` is already a route,
so `/jobs/bulk/publish` would be captured by it with `bulk` as the slug if this router were
included after. `tests/test_bulk_upload.py` asserts the order.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.marketplace import bulk, schemas

router = APIRouter(prefix="/org/{org_slug}", tags=["bulk"])

CanCreateJob = Depends(require(Permission.JOB_CREATE, "job"))
CanPublishJob = Depends(require(Permission.JOB_PUBLISH, "job"))
CanCreateCourse = Depends(require(Permission.COURSE_CREATE, "course"))
CanPublishCourse = Depends(require(Permission.COURSE_PUBLISH, "course"))


# The file is the request body, read raw -- so FastAPI cannot see it. Declaring it here is what
# puts `text/csv` in the OpenAPI document and a `string` body in the generated client.
_CSV_BODY: dict[str, object] = {
    "requestBody": {
        "required": True,
        "content": {"text/csv": {"schema": {"type": "string"}}},
    }
}


def _out(report: bulk.BulkReport) -> schemas.BulkReportOut:
    return schemas.BulkReportOut(
        kind=report.kind,
        applied=report.applied,
        rows=[
            schemas.BulkRowOut(
                row=r.row,
                status=r.status,
                title=r.title,
                external_ref=r.external_ref,
                messages=r.messages,
                standards=[
                    schemas.BulkStandardOut(
                        code=s.code,
                        name=s.name,
                        origin=s.origin,
                        importance=s.importance if report.kind == "jobs" else None,
                        mandatory=s.mandatory if report.kind == "jobs" else None,
                        level=s.level if report.kind == "courses" else None,
                    )
                    for s in r.standards
                ],
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
        daily_limit=report.daily_limit,
        remaining_today=report.remaining_today,
        errors_csv=report.errors_csv,
    )


async def _file(
    request: Request,
    db: AsyncSession,
    context: TenantContext,
    kind: Literal["jobs", "courses"],
    *,
    apply: bool,
) -> schemas.BulkReportOut:
    try:
        text = bulk.decode(await request.body())
        report = await bulk.run(
            db, kind, context.tenant, text, apply=apply, actor_id=context.user.id
        )
    except bulk.BulkFileError as error:
        raise HTTPException(error.status_code, error.message) from error
    return _out(report)


def _csv(kind: Literal["jobs", "courses"]) -> Response:
    return Response(
        bulk.template_csv(kind),
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="{kind}-template.csv"'},
    )


async def _publish(
    db: AsyncSession,
    context: TenantContext,
    kind: Literal["jobs", "courses"],
    payload: schemas.BulkPublishIn,
) -> schemas.BulkPublishOut:
    results = await bulk.publish_many(db, kind, context.tenant.id, payload.slugs)
    return schemas.BulkPublishOut(
        results=[
            schemas.BulkPublishRowOut(slug=r.slug, published=r.published, message=r.message)
            for r in results
        ],
        published=sum(1 for r in results if r.published),
        refused=sum(1 for r in results if not r.published),
    )


# ---------------------------------------------------------------- vacancies


@router.get("/jobs/bulk/template")
async def jobs_template(context: TenantContext = CanCreateJob) -> Response:
    """The columns, with two example rows. Served here so there is one list of them."""
    return _csv("jobs")


@router.post("/jobs/bulk/check", response_model=schemas.BulkReportOut, openapi_extra=_CSV_BODY)
async def check_jobs(
    request: Request,
    context: TenantContext = CanCreateJob,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.BulkReportOut:
    """Validate every row and say what an apply would do. Writes nothing."""
    return await _file(request, db, context, "jobs", apply=False)


@router.post("/jobs/bulk/apply", response_model=schemas.BulkReportOut, openapi_extra=_CSV_BODY)
async def apply_jobs(
    request: Request,
    context: TenantContext = CanCreateJob,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.BulkReportOut:
    """Check the file again, then create each valid row as a **draft**. Never publishes."""
    return await _file(request, db, context, "jobs", apply=True)


@router.post("/jobs/bulk/publish", response_model=schemas.BulkPublishOut)
async def publish_jobs(
    payload: schemas.BulkPublishIn,
    context: TenantContext = CanPublishJob,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.BulkPublishOut:
    """Publish a batch through the single route's own rules, reporting each refusal."""
    return await _publish(db, context, "jobs", payload)


# ------------------------------------------------------------------ courses


@router.get("/courses/bulk/template")
async def courses_template(context: TenantContext = CanCreateCourse) -> Response:
    return _csv("courses")


@router.post("/courses/bulk/check", response_model=schemas.BulkReportOut, openapi_extra=_CSV_BODY)
async def check_courses(
    request: Request,
    context: TenantContext = CanCreateCourse,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.BulkReportOut:
    return await _file(request, db, context, "courses", apply=False)


@router.post("/courses/bulk/apply", response_model=schemas.BulkReportOut, openapi_extra=_CSV_BODY)
async def apply_courses(
    request: Request,
    context: TenantContext = CanCreateCourse,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.BulkReportOut:
    return await _file(request, db, context, "courses", apply=True)


@router.post("/courses/bulk/publish", response_model=schemas.BulkPublishOut)
async def publish_courses(
    payload: schemas.BulkPublishIn,
    context: TenantContext = CanPublishCourse,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.BulkPublishOut:
    return await _publish(db, context, "courses", payload)
