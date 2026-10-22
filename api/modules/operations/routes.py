import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import OperatorContext, Permission, require_operator
from api.core.database import get_db_session
from api.modules import skills
from api.modules.identity.schemas import OrgTenantType
from api.modules.marketplace.bulk import BulkFileError, decode
from api.modules.operations import enrolment, schemas, service, skill_gap

router = APIRouter(prefix="/ops", tags=["operations"])

# Built once at import, the idiom `publishing_routes.py` uses and for its
# reasons -- constructing the dependency per call is wasteful and is what B008
# catches. Here it buys one thing more: `require_operator` raises at import if
# handed a non-operator permission, so a mistake is a boot failure rather than
# a route that 404s for ever and reads as missing.
CanReadOrgs = Depends(require_operator(Permission.OPS_ORG_READ))
CanVerifyOrgs = Depends(require_operator(Permission.OPS_ORG_VERIFY))
CanReadProgrammes = Depends(require_operator(Permission.OPS_PROGRAMME_READ))
CanVerifyCandidates = Depends(require_operator(Permission.OPS_CANDIDATE_VERIFY))
CanEditAliases = Depends(require_operator(Permission.OPS_ALIAS_EDIT))
CanEnrol = Depends(require_operator(Permission.OPS_ENROL))


@router.get("/organisations", response_model=schemas.OrganisationQueue)
async def verification_queue(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=100),
    kind: OrgTenantType | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadOrgs,
) -> schemas.OrganisationQueue:
    """Organisations awaiting a verification decision, oldest first, and how many match.

    `q` searches name, slug and city; `kind` narrows to one organisation type (Sprint 93, BL-22.8).
    Neither given, `total` is every organisation waiting, which is the overview tile's figure.
    """
    rows, total = await service.unverified_organisations(
        db, limit=limit, offset=offset, q=q, kind=kind
    )
    items = [
        schemas.UnverifiedOrganisation(
            slug=tenant.slug,
            name=tenant.name,
            tenant_type=tenant.tenant_type,
            city=tenant.city,
            website=tenant.website,
            created_at=tenant.created_at,
            jobs=jobs,
            courses=courses,
            members=members,
        )
        for tenant, jobs, courses, members in rows
    ]
    return schemas.OrganisationQueue(items=items, total=total, limit=limit, offset=offset)


@router.get("/dashboard", response_model=schemas.PlatformDashboardOut)
async def dashboard(
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadOrgs,
) -> schemas.PlatformDashboardOut:
    """An operator's landing numbers (Sprint 39, BL-10.4) -- today there is
    none; sign-in opens straight onto the verification queue.

    `scarce_skills` (Sprint 40) is built explicitly rather than folded into
    `model_validate`: `ScarceSkillOut` carries no `from_attributes` config,
    matching how the provider-facing market router already builds it in
    `matching/provider_routes.py`."""
    data = await service.platform_dashboard(db)
    return schemas.PlatformDashboardOut(
        unverified_organisations=data.unverified_organisations,
        unverified_certifications=data.unverified_certifications,
        organisations=data.organisations,
        candidates=data.candidates,
        published_jobs=data.published_jobs,
        published_courses=data.published_courses,
        scarce_skills=[schemas.ScarceSkillOut(**vars(s)) for s in data.scarce_skills],
    )


@router.get(
    "/organisations/{org_slug}/verification",
    response_model=schemas.OrganisationVerificationOut,
)
async def verification_detail(
    org_slug: str,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadOrgs,
) -> schemas.OrganisationVerificationOut:
    """The current badge and every decision behind it."""
    tenant = await service.organisation_for_review(db, org_slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    return _detail(tenant, await service.verification_history(db, tenant.id))


@router.post(
    "/organisations/{org_slug}/verification",
    response_model=schemas.OrganisationVerificationOut,
)
async def decide_verification(
    org_slug: str,
    payload: schemas.VerificationIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanVerifyOrgs,
) -> schemas.OrganisationVerificationOut:
    """Grant or revoke, with the evidence.

    One route rather than two, because they are one decision with two values:
    a second endpoint would carry a second copy of the note and a second way to
    forget it.
    """
    tenant = await service.organisation_for_review(db, org_slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    await service.set_verification(
        db, tenant, decision=payload.decision, note=payload.note, actor=context.user
    )
    return _detail(tenant, await service.verification_history(db, tenant.id))


@router.get("/candidates/certifications", response_model=schemas.CertificationQueue)
async def certification_queue(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanVerifyCandidates,
) -> schemas.CertificationQueue:
    """Certifications naming a standard, awaiting a decision (Sprint 35, BL-3.2), and how many
    wait in all."""
    rows, total = await service.unverified_certifications(db, limit=limit, offset=offset)
    items = [
        schemas.UnverifiedCertification(
            id=cert.id,
            candidate_name=candidate_name,
            name=cert.name,
            issuing_body=cert.issuing_body,
            credential_id=cert.credential_id,
            # Guaranteed non-null: the queue query itself filters on
            # `skill_id IS NOT NULL`.
            skill_slug=cert.skill.slug,  # type: ignore[union-attr]
            skill_name=cert.skill.name,  # type: ignore[union-attr]
        )
        for cert, candidate_name in rows
    ]
    return schemas.CertificationQueue(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/candidates/certifications/{certification_id}/verify",
    response_model=schemas.VerifiedCertificationOut,
)
async def verify_certification(
    certification_id: uuid.UUID,
    payload: schemas.CertificationVerifyIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanVerifyCandidates,
) -> schemas.VerifiedCertificationOut:
    """Sets `CandidateSkill.source='certified'` for the standard this
    certification names (Sprint 35, BL-3.2) -- the non-seed writer
    `docs/scope-reconciliation.md`'s postscript asks for."""
    certification = await service.certification_for_review(db, certification_id)
    if certification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    certification = await service.verify_certification(
        db, certification, note=payload.note, actor=context.user
    )
    return schemas.VerifiedCertificationOut(
        id=certification.id,
        name=certification.name,
        skill_slug=certification.skill.slug,  # type: ignore[union-attr]
        verified_at=certification.verified_at,
        verification_note=certification.verification_note,
    )


@router.get("/programmes", response_model=schemas.KnownProgrammesOut)
async def list_programmes(
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadProgrammes,
) -> schemas.KnownProgrammesOut:
    """Every programme name worth offering as a starting point (Sprint 39,
    BL-10.5). Declared before `/programmes/{name}` or the literal path would be
    captured as a name."""
    return schemas.KnownProgrammesOut(programmes=await service.known_programmes(db))


@router.get("/programmes/{name}", response_model=schemas.ProgrammeReportOut)
async def programme_report(
    name: str,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadProgrammes,
) -> schemas.ProgrammeReportOut:
    """Outcomes for one government-agency programme, by name (Sprint 33).

    Stands in for an agency's own login, which does not exist yet -- an
    operator views this on the agency's behalf. Always 200: a programme name
    is free text (`CandidateProfile.enrolled_via_programme`'s docstring), not
    a resource with its own row to 404 against, so an unrecognised name simply
    reports zero.
    """
    report = await service.programme_report(db, name)
    return schemas.ProgrammeReportOut.model_validate(report)


@router.get("/programmes/{name}/districts", response_model=schemas.ProgrammeDistrictsOut)
async def programme_districts(
    name: str,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadProgrammes,
) -> schemas.ProgrammeDistrictsOut:
    """A programme's enrolment, by district (Sprint 40).

    A separate, heavier `GROUP BY` from `programme_report`'s own four
    numbers -- a caller that only wants those should not pay for this query
    too on every call."""
    rows = await service.programme_by_district(db, name)
    return schemas.ProgrammeDistrictsOut(
        programme=name,
        minimum_cell=skill_gap.MIN_CELL_SIZE,
        districts=[
            schemas.DistrictBreakdownOut(
                district=r.district, enrolled=r.enrolled, below_minimum=r.below_minimum
            )
            for r in rows
        ],
    )


@router.get("/districts", response_model=schemas.DistrictOptionsOut)
async def districts_with_demand(
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadProgrammes,
) -> schemas.DistrictOptionsOut:
    """Districts with an open vacancy, for the skill-gap picker (Sprint 49, BL-12.7)."""
    rows = await skill_gap.districts_with_demand(db)
    return schemas.DistrictOptionsOut(
        districts=[
            schemas.DistrictOptionOut(
                id=r.district_id, name=r.district, state=r.state, vacancies=r.vacancies
            )
            for r in rows
        ]
    )


@router.get("/districts/{district_id}/skill-gap", response_model=schemas.DistrictSkillGapOut)
async def district_skill_gap(
    district_id: uuid.UUID,
    limit: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadProgrammes,
) -> schemas.DistrictSkillGapOut:
    """Where one district's open vacancies ask for standards its residents do not hold,
    ranked by shortfall (Sprint 49, BL-12.7). Counts of one to four residents are not
    shown -- see `operations.skill_gap`."""
    gap = await skill_gap.district_skill_gap(db, district_id, limit=limit)
    if gap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    return schemas.DistrictSkillGapOut(
        district=schemas.DistrictOptionOut(
            id=gap.district_id, name=gap.district, state=gap.state, vacancies=gap.vacancies
        ),
        positions=gap.positions,
        residents=gap.residents,
        residents_below_minimum=gap.residents_below_minimum,
        minimum_cell=skill_gap.MIN_CELL_SIZE,
        standards=[
            schemas.DistrictGapRowOut(
                nos_code=r.nos_code,
                name=r.name,
                vacancies=r.vacancies,
                demand=r.demand,
                supply=r.supply,
                supply_below_minimum=r.supply_below_minimum,
                shortfall=r.shortfall,
                shortfall_is_minimum=r.shortfall_is_minimum,
            )
            for r in gap.standards
        ],
    )


def _detail(tenant, history) -> schemas.OrganisationVerificationOut:  # type: ignore[no-untyped-def]
    return schemas.OrganisationVerificationOut(
        slug=tenant.slug,
        name=tenant.name,
        is_verified=tenant.is_verified,
        verified_at=tenant.verified_at,
        verification_note=tenant.verification_note,
        history=[
            schemas.VerificationEventOut(
                id=event.id,
                decision=event.decision,
                note=event.note,
                created_at=event.created_at,
                actor_name=name,
            )
            for event, name in history
        ],
    )


# ------------------------------------------------------------ role aliases (Sprint 47)
#
# The rules and the writes are `skills.alias_admin`'s; these routes carry the permission and
# nothing else. Declared before nothing and after everything: none of these paths collides with
# a `/ops/organisations` or `/ops/programmes` route.


def _check_out(check: skills.AliasCheck) -> schemas.RoleAliasCheckOut:
    return schemas.RoleAliasCheckOut(
        ok=check.ok,
        surface_form=check.surface_form,
        target=schemas.AliasTargetOut(**vars(check.target)) if check.target else None,
        problems=check.problems,
        warnings=check.warnings,
        existing=check.existing,
    )


@router.get("/role-aliases", response_model=schemas.RoleAliasListOut)
async def list_role_aliases(
    q: str | None = Query(None, max_length=80),
    limit: int = Query(100, ge=1, le=300),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEditAliases,
) -> schemas.RoleAliasListOut:
    """Live aliases, alphabetical, filtered by the term or its target."""
    rows, total = await skills.list_aliases(db, query=q, limit=limit)
    return schemas.RoleAliasListOut(
        items=[schemas.RoleAliasOut.model_validate(r) for r in rows], total=total
    )


@router.post("/role-aliases/check", response_model=schemas.RoleAliasCheckOut)
async def check_role_alias(
    payload: schemas.RoleAliasIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEditAliases,
) -> schemas.RoleAliasCheckOut:
    """Dry run: the same checks `POST /role-aliases` applies, and nothing written."""
    return _check_out(await skills.check_alias(db, payload.surface_form, payload.job_role))


@router.post(
    "/role-aliases", response_model=schemas.RoleAliasOut, status_code=status.HTTP_201_CREATED
)
async def add_role_alias(
    payload: schemas.RoleAliasIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEditAliases,
) -> schemas.RoleAliasOut:
    """Add an alias, or revive a retired one. 422 if it would be wrong, 409 if the term is taken."""
    alias = await skills.add_alias(
        db,
        surface_form=payload.surface_form,
        job_role=payload.job_role,
        note=payload.note,
        actor_user_id=context.user.id,
    )
    return schemas.RoleAliasOut.model_validate(alias)


@router.post("/role-aliases/{alias_id}/retire", response_model=schemas.RoleAliasOut)
async def retire_role_alias(
    alias_id: uuid.UUID,
    payload: schemas.RoleAliasRetireIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEditAliases,
) -> schemas.RoleAliasOut:
    """Withdraw an alias. Kept, not deleted, so a seed that still names it cannot bring it back."""
    alias = await skills.retire_alias(
        db, alias_id, note=payload.note, actor_user_id=context.user.id
    )
    return schemas.RoleAliasOut.model_validate(alias)


@router.get("/role-aliases/history", response_model=list[schemas.RoleAliasEventOut])
async def role_alias_history(
    limit: int = Query(30, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEditAliases,
) -> list[schemas.RoleAliasEventOut]:
    """The most recent operator decisions about aliases, newest first."""
    return [
        schemas.RoleAliasEventOut.model_validate(e)
        for e in await skills.recent_events(db, limit=limit)
    ]


# ------------------------------------------------------------- agency enrolment (Sprint 61)

# The file is the request body, read raw (the Sprint 51 shape): FastAPI cannot see it, so declaring
# it here is what puts `text/csv` in the OpenAPI document and a `string` body in the client.
_CSV_BODY: dict[str, object] = {
    "requestBody": {"required": True, "content": {"text/csv": {"schema": {"type": "string"}}}}
}


def _enrolment_out(report: enrolment.EnrolmentReport) -> schemas.EnrolmentReportOut:
    return schemas.EnrolmentReportOut(
        programme=report.programme,
        applied=report.applied,
        rows=[
            schemas.EnrolmentRowOut(
                row=r.row,
                status=r.status,
                phone=r.phone,
                first_name=r.first_name,
                warnings=r.warnings,
                errors=r.errors,
            )
            for r in report.rows
        ],
        notes=report.notes,
        new=report.count("new"),
        tag=report.count("tag"),
        already=report.count("already"),
        errors=report.count("error"),
        errors_csv=report.errors_csv,
        batch_id=report.batch_id,
    )


async def _enrol(
    request: Request,
    db: AsyncSession,
    context: OperatorContext,
    *,
    programme: str,
    apply: bool,
    attested: bool,
    file_name: str | None,
) -> schemas.EnrolmentReportOut:
    try:
        report = await enrolment.run(
            db,
            decode(await request.body()),
            programme=programme,
            apply=apply,
            attested=attested,
            actor=context.user,
            file_name=file_name,
        )
    except BulkFileError as error:
        raise HTTPException(error.status_code, error.message) from error
    return _enrolment_out(report)


@router.get("/enrolment/template")
async def enrolment_template(context: OperatorContext = CanEnrol) -> Response:
    """The columns, with two example rows. Served here so there is one list of them."""
    return Response(
        enrolment.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": 'attachment; filename="enrolment-template.csv"'},
    )


@router.post(
    "/enrolment/check",
    response_model=schemas.EnrolmentReportOut,
    openapi_extra=_CSV_BODY,
)
async def check_enrolment(
    request: Request,
    programme: str = Query(..., max_length=200),
    file_name: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEnrol,
) -> schemas.EnrolmentReportOut:
    """Say what an enrolment of this file would do, row by row. **Writes nothing.**"""
    return await _enrol(
        request,
        db,
        context,
        programme=programme,
        apply=False,
        attested=False,
        file_name=file_name,
    )


@router.post(
    "/enrolment/apply",
    response_model=schemas.EnrolmentReportOut,
    openapi_extra=_CSV_BODY,
)
async def apply_enrolment(
    request: Request,
    programme: str = Query(..., max_length=200),
    attest: bool = Query(
        False,
        description="The operator confirms the privacy notice was read out to everyone enrolled.",
    ),
    file_name: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEnrol,
) -> schemas.EnrolmentReportOut:
    """Check the file again, then enrol it. Refused (422, nothing written) without `attest`."""
    return await _enrol(
        request,
        db,
        context,
        programme=programme,
        apply=True,
        attested=attest,
        file_name=file_name,
    )


@router.get("/enrolment/batches", response_model=schemas.EnrolmentBatchesOut)
async def enrolment_batches(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanEnrol,
) -> schemas.EnrolmentBatchesOut:
    """Recent enrolments, newest first, with who attested and which notice version."""
    rows = await enrolment.recent_batches(db, limit=limit)
    return schemas.EnrolmentBatchesOut(batches=[schemas.EnrolmentBatchOut(**vars(b)) for b in rows])
