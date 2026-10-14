"""Bulk-enrol candidates on behalf of a government agency, from the command line (Sprint 33,
BL-7.1; the engine moved in Sprint 61, BL-14.10, ADR-071).

**This is a thin caller.** The rules live in `api/modules/operations/enrolment.py` and are the same
ones the back office's upload runs: one phone check, one "never overwrite", one attestation. This
script reads a file, names the operator, and prints the report.

**An enrolment is attested.** The current privacy notice is stamped against every person created, so
someone has to say it was read out to them. `--apply` therefore needs `--attest` and
`--operator-email`, an admin-tier operator already granted staff (`scripts/grant_staff.py`); the
batch records who. Without `--apply` this is a dry run, exactly the upload's *check*, and writes
nothing.

CSV columns (header row required, only `phone` is required): phone, full_name, headline, state,
district, years_experience. See scripts/fixtures/sample_programme_enrolment.csv for the shape.

    .venv/bin/python scripts/bulk_enrol_candidates.py \\
        scripts/fixtures/sample_programme_enrolment.csv "PMKVY-2026-TN-Batch1"
    .venv/bin/python scripts/bulk_enrol_candidates.py \\
        scripts/fixtures/sample_programme_enrolment.csv "PMKVY-2026-TN-Batch1" \\
        --apply --attest --operator-email ops@example.org
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import dispose_engine, get_sessionmaker
from api.core.logging import configure_logging
from api.modules.identity.models import User
from api.modules.marketplace.bulk import BulkFileError, decode
from api.modules.operations import enrolment


async def enrol_file(
    db: AsyncSession,
    path: Path,
    programme: str,
    *,
    apply: bool,
    attest: bool,
    operator_email: str | None,
) -> enrolment.EnrolmentReport:
    """Run the file through the engine. A dry run needs no operator; an apply needs an admin."""
    actor = None
    if operator_email:
        actor = await db.scalar(select(User).where(User.email == operator_email.strip().lower()))
    if apply and (actor is None or not actor.is_staff or actor.staff_tier != "admin"):
        raise BulkFileError(
            "--apply needs --operator-email naming an admin-tier operator "
            "(see scripts/grant_staff.py)."
        )
    if actor is None:
        # A dry run writes nothing, but the engine wants somebody to attribute an apply to.
        actor = User(email="dry-run@invalid.example")
    return await enrolment.run(
        db,
        decode(await asyncio.to_thread(path.read_bytes)),
        programme=programme,
        apply=apply,
        attested=attest,
        actor=actor,
        file_name=path.name,
    )


def _print(report: enrolment.EnrolmentReport) -> None:
    label = "Enrolled" if report.applied else "DRY RUN -- would enrol"
    print(f"{label}, programme {report.programme!r}, {len(report.rows)} rows read:")
    print(f"  new candidates:       {report.count('new')}")
    print(f"  existing, now tagged: {report.count('tag')}")
    print(f"  already enrolled:     {report.count('already')}")
    print(f"  errors:               {report.count('error')}")
    for row in report.rows:
        for message in (*row.errors, *row.warnings):
            print(f"  row {row.row} ({row.phone}): {message}", file=sys.stderr)
    if not report.applied:
        print("\nRe-run with --apply --attest --operator-email <admin> to write.")


async def _run(args: argparse.Namespace) -> int:
    configure_logging()
    try:
        async with get_sessionmaker()() as db:
            report = await enrol_file(
                db,
                args.csv_path,
                args.programme,
                apply=args.apply,
                attest=args.attest,
                operator_email=args.operator_email,
            )
            if not args.apply:
                await db.rollback()
    except BulkFileError as error:
        print(error.message, file=sys.stderr)
        return 1
    finally:
        await dispose_engine()
    _print(report)
    return 1 if report.count("error") else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="path to the enrolment CSV")
    parser.add_argument("programme", help="the programme name to tag every row with")
    parser.add_argument("--apply", action="store_true", help="write; otherwise this is a dry run")
    parser.add_argument(
        "--attest",
        action="store_true",
        help="the privacy notice was read out to everyone in the file (needed with --apply)",
    )
    parser.add_argument("--operator-email", help="the admin-tier operator enrolling the file")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
