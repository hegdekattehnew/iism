"""Remove the organisations that test sessions left behind.

Nineteen sprints of browser checks and probes left fixture organisations in the
development database -- "S18 TNT", "Logging Clinic 4f86a7", "Fresh Org" -- which
would appear in a switcher or a list during a demo.

**Two rules, and both matter more than the tidying.**

*Named, never matched.* The list below is explicit. A pattern over names would
be shorter and would eventually match something real: this database holds the
owner's own account and organisations, and "TNT" is the company's own name.

*Organisations only, never accounts.* Deleting a tenant costs somebody a
membership they can recreate in a minute. Deleting a user destroys a profile,
its history and its applications. Where the two are ambiguous -- and a fixture
organisation created by a real person is exactly that -- the script removes the
organisation and leaves the person, reporting whose membership went.

Dry run by default:

    .venv/bin/python scripts/clean_fixtures.py            # says what would go
    .venv/bin/python scripts/clean_fixtures.py --apply    # does it
"""

import asyncio
import sys

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import dispose_engine, get_sessionmaker
from api.core.localisation import ContentTranslation
from api.modules.applications.models import Application, SavedJob
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace.models import Course, CourseSkill, Job, JobSkill
from api.modules.notifications.models import Notification

# Exactly what goes. Slugs, because a name can be edited from the interface and
# a slug cannot -- `tenant_type` and `slug` are both absent from `OrganisationIn`
# for that reason.
FIXTURE_SLUGS = [
    "fresh-org",
    "logging-clinic-4f86a7",
    "lotus-hospitals-bengaluru",
    "meridian-care-hospitals",
    "priya-care-services",
    "s18-org-only-575c77",
    "s18-tnt",
    "s18-tnt-edu",
    "sprint16-clinic-e9bb88",
    "sunrise-clinic-pune",
    "tnt",
    "tnt-edu",
    "vidya-skills-institute",
]


async def _describe(db: AsyncSession, tenant: Tenant) -> str:
    jobs = await db.scalar(select(func.count()).select_from(Job).where(Job.tenant_id == tenant.id))
    courses = await db.scalar(
        select(func.count()).select_from(Course).where(Course.tenant_id == tenant.id)
    )
    members = (
        await db.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.tenant_id == tenant.id)
        )
    ).all()
    who = ", ".join(u.email or u.phone or str(u.id)[:8] for u in members) or "nobody"
    return (
        f"{tenant.slug:<28} {tenant.tenant_type:<15} "
        f"jobs={jobs} courses={courses} members={len(members)} ({who})"
    )


async def _remove(db: AsyncSession, tenant: Tenant) -> None:
    """Everything the organisation owns, then the organisation.

    Explicit, in dependency order, rather than trusting cascades -- the same
    reason `api/modules/privacy/service.py` deletes table by table. Translations
    and notifications have no foreign key to cascade from at all.
    """
    job_ids = list((await db.scalars(select(Job.id).where(Job.tenant_id == tenant.id))).all())
    course_ids = list(
        (await db.scalars(select(Course.id).where(Course.tenant_id == tenant.id))).all()
    )

    if job_ids:
        await db.execute(delete(Application).where(Application.job_id.in_(job_ids)))
        await db.execute(delete(SavedJob).where(SavedJob.job_id.in_(job_ids)))
        await db.execute(delete(JobSkill).where(JobSkill.job_id.in_(job_ids)))
        await db.execute(
            delete(ContentTranslation).where(
                ContentTranslation.entity_type == "job",
                ContentTranslation.entity_id.in_(job_ids),
            )
        )
        await db.execute(delete(Job).where(Job.id.in_(job_ids)))
    if course_ids:
        await db.execute(delete(CourseSkill).where(CourseSkill.course_id.in_(course_ids)))
        await db.execute(
            delete(ContentTranslation).where(
                ContentTranslation.entity_type == "course",
                ContentTranslation.entity_id.in_(course_ids),
            )
        )
        await db.execute(delete(Course).where(Course.id.in_(course_ids)))

    await db.execute(
        delete(Notification).where(
            Notification.recipient_kind == "tenant", Notification.recipient_id == tenant.id
        )
    )
    # The membership goes; the person stays. See this module's docstring.
    await db.execute(delete(Membership).where(Membership.tenant_id == tenant.id))
    await db.execute(delete(Tenant).where(Tenant.id == tenant.id))


async def main() -> None:
    apply = "--apply" in sys.argv
    async with get_sessionmaker()() as db:
        tenants = list(
            (await db.scalars(select(Tenant).where(Tenant.slug.in_(FIXTURE_SLUGS)))).all()
        )
        missing = sorted(set(FIXTURE_SLUGS) - {t.slug for t in tenants})

        print(f"{'WOULD REMOVE' if not apply else 'REMOVING'} {len(tenants)} organisation(s):\n")
        for tenant in sorted(tenants, key=lambda t: t.slug):
            print("  " + await _describe(db, tenant))
        if missing:
            print("\nnot present (already gone, or never here):")
            for slug in missing:
                print(f"  {slug}")

        if not apply:
            print("\nDry run. Nothing was changed. Re-run with --apply to remove them.")
            print("No user account is deleted by this script, with or without --apply.")
            await dispose_engine()
            return

        for tenant in tenants:
            await _remove(db, tenant)
        await db.commit()
        print(f"\nRemoved {len(tenants)} organisation(s). No account was deleted.")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
