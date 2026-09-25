"""Bulk-enrol candidates on behalf of a government agency (Sprint 33, BL-7.1).

**The thin slice, not the production version.** No self-service portal, no
multi-format import, no new account-construction path: this calls
`identity.service.provision_candidate` -- the same function
`scripts/seed_candidates.py` uses -- so there is exactly one place a `User` is
ever built from nothing. What this script adds on top is a CSV reader, a
programme tag, and a report.

**Consent is recorded, not assumed away.** A real agency enrolment happens
through a physical or assisted channel where the current privacy notice is
read out and agreed to before any data is typed in -- this script records that
consent against today's `PRIVACY_NOTICE_VERSION` on the same footing as a
self-registered sign-up. It does not verify that the conversation happened;
that is the agency's responsibility, the same way an employer is trusted to
have a candidate's permission before an operator manually adjusts a record.

**Idempotent by phone, and safe to re-run.** A number already on the platform
is never re-provisioned and its existing profile fields are never touched --
only tagged with the programme, and only if it carries no tag yet. A number
seen for the first time is enrolled in full.

CSV columns (header row required): phone, full_name, headline, state,
district, years_experience. See scripts/fixtures/sample_programme_enrolment.csv
for the shape.

Dry run by default:

    .venv/bin/python scripts/bulk_enrol_candidates.py \\
        scripts/fixtures/sample_programme_enrolment.csv "PMKVY-2026-TN-Batch1"
    .venv/bin/python scripts/bulk_enrol_candidates.py \\
        scripts/fixtures/sample_programme_enrolment.csv "PMKVY-2026-TN-Batch1" --apply
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION
from api.core.database import dispose_engine, get_sessionmaker
from api.core.logging import configure_logging
from api.modules.geography import resolve_location
from api.modules.identity.models import User
from api.modules.identity.schemas import normalise_phone
from api.modules.identity.service import provision_candidate
from api.modules.marketplace.models import CandidateProfile

REQUIRED_COLUMNS = {"phone", "full_name", "headline", "state", "district", "years_experience"}


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            print(f"CSV is missing columns: {', '.join(sorted(missing))}", file=sys.stderr)
            raise SystemExit(1)
        return list(reader)


async def _enrol_one(db: AsyncSession, row: dict[str, str], programme: str, *, apply: bool) -> str:
    """Returns one of: 'created', 'tagged', 'already_enrolled'.

    Raises `ValueError` on a malformed row (a non-numeric years_experience, a
    phone that normalises to nothing usable) — the caller catches this per
    row, so one bad row in a partner-supplied CSV costs one row, not the batch.
    """
    phone = normalise_phone(row["phone"])
    if len(phone) < 8:
        raise ValueError(f"unusable phone: {row['phone']!r}")
    user = await db.scalar(select(User).where(User.phone == phone))

    if user is not None:
        profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        )
        if profile is not None and profile.enrolled_via_programme:
            return "already_enrolled"
        if not apply:
            return "tagged"
        if profile is None:
            # An account exists (they signed up themselves) but never finished
            # a profile. Give them one rather than skipping -- the programme
            # tag would otherwise point at nothing.
            profile = CandidateProfile(user_id=user.id)
            db.add(profile)
        profile.enrolled_via_programme = programme
        await db.flush()
        return "tagged"

    if not apply:
        return "created"

    user = await provision_candidate(db, phone, consent_version=PRIVACY_NOTICE_VERSION)
    user.full_name = row["full_name"].strip() or None
    profile = CandidateProfile(
        user_id=user.id,
        headline=row["headline"].strip() or None,
        location_state=row["state"].strip() or None,
        location_district=row["district"].strip() or None,
        years_experience=int(row["years_experience"] or 0),
        enrolled_via_programme=programme,
    )
    db.add(profile)
    await db.flush()

    located = await resolve_location(db, row["state"].strip(), row["district"].strip())
    profile.state_id, profile.district_id = located.state_id, located.district_id
    await db.flush()
    return "created"


async def _run(csv_path: Path, programme: str, *, apply: bool) -> int:
    configure_logging()
    rows = _read_rows(csv_path)
    if not rows:
        print("CSV has no data rows.", file=sys.stderr)
        return 1

    counts = {"created": 0, "tagged": 0, "already_enrolled": 0, "errors": 0}
    async with get_sessionmaker()() as db:
        for i, row in enumerate(rows, start=2):  # row 1 is the header
            try:
                outcome = await _enrol_one(db, row, programme, apply=apply)
            except (ValueError, KeyError) as exc:
                print(f"  row {i} ({row.get('phone', '?')!r}): {exc}", file=sys.stderr)
                counts["errors"] += 1
                continue
            counts[outcome] = counts.get(outcome, 0) + 1
        if apply:
            await db.commit()
        else:
            await db.rollback()
    await dispose_engine()

    label = "DRY RUN — would" if not apply else "Enrolled"
    print(f"{label}, programme {programme!r}, {len(rows)} rows read:")
    print(f"  new candidates:       {counts['created']}")
    print(f"  existing, now tagged: {counts['tagged']}")
    print(f"  already enrolled:     {counts['already_enrolled']}")
    print(f"  errors:               {counts['errors']}")
    if not apply:
        print("\nRe-run with --apply to write.")
    return 1 if counts["errors"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="path to the enrolment CSV")
    parser.add_argument("programme", help="the programme name to tag every row with")
    parser.add_argument("--apply", action="store_true", help="write; otherwise this is a dry run")
    args = parser.parse_args()
    return asyncio.run(_run(args.csv_path, args.programme, apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
