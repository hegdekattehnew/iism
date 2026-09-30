import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import OperatorContext, Permission, require_operator
from api.core.database import get_db_session
from api.modules.operations import schemas, service

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


@router.get("/organisations", response_model=list[schemas.UnverifiedOrganisation])
async def verification_queue(
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanReadOrgs,
) -> list[schemas.UnverifiedOrganisation]:
    """Organisations awaiting a verification decision, oldest first."""
    rows = await service.unverified_organisations(db, limit=limit)
    return [
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


@router.get("/candidates/certifications", response_model=list[schemas.UnverifiedCertification])
async def certification_queue(
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanVerifyCandidates,
) -> list[schemas.UnverifiedCertification]:
    """Certifications naming a standard, awaiting a decision (Sprint 35, BL-3.2)."""
    rows = await service.unverified_certifications(db, limit=limit)
    return [
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
        districts=[
            schemas.DistrictBreakdownOut(district=r.district, enrolled=r.enrolled) for r in rows
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
