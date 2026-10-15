"""Create the demonstration account a store reviewer signs in to (Sprint 65, BL-15.8, ADR-076).

The reviewers' fixed code (`REVIEWER_CODE`, for the phones in `REVIEWER_PHONES`) opens **only a
demonstration account**: a candidate with a name, a place and a few declared standards, so that the
reviewer sees matches and can apply. This makes that account. It deliberately does less than it
could:

* **It only ever creates.** A phone that already has an account is an error and nothing is written:
  a script that could adopt a real person's number as a reviewer account would be the hole the
  login refuses to open.
* **The consent is attested, not assumed** (ADR-071): `--attest` says the privacy notice was shown
  to whoever will use this account, which for a store reviewer is the submission's own note. The
  notice version in force is recorded against the account.
* **It never makes anybody staff or gives them an organisation**, so verification, which refuses
  both for a reviewer phone, will accept it.

Dry run by default:

    .venv/bin/python scripts/create_reviewer.py --phone +919876543210
    .venv/bin/python scripts/create_reviewer.py --phone +919876543210 --apply --attest

The phone must also be in `REVIEWER_PHONES` of the deployment, and `REVIEWER_LOGIN_ENABLED` on.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.database import dispose_engine, get_sessionmaker
from api.core.logging import configure_logging
from api.modules.identity.schemas import normalise_phone
from api.modules.identity.service import provision_candidate
from api.modules.marketplace.profile_service import add_skills_bulk, update_profile
from api.modules.skills.models import Skill

NAME = "Store Reviewer"
HEADLINE = "Demonstration account for store review"
STATE, DISTRICT = "Tamil Nadu", "Chennai"
# National Occupational Standards of the General Duty Assistant qualification: enough declared
# skills that the matches screen has something to show, as the seeded demonstration candidates do.
NOS_CODES = ("HSS/N6012", "HSS/N6002", "HSS/N9618", "HSS/N6003", "HSS/N9614")


@dataclass
class Outcome:
    created: bool
    phone: str
    skills: int


class ReviewerError(Exception):
    """Nothing was written, and this says why."""


async def create_reviewer(
    db: AsyncSession, raw_phone: str, *, apply: bool, attest: bool
) -> Outcome:
    phone = normalise_phone(raw_phone)
    if len(phone) != 13:
        raise ReviewerError(f"{raw_phone!r} is not an Indian mobile number")
    if apply and not attest:
        raise ReviewerError(
            "--apply needs --attest: the privacy notice must have been shown to whoever uses "
            "this account."
        )
    # Imported here because it reads the User model, which needs the identity module loaded.
    from api.modules.identity.models import User

    if await db.scalar(select(User.id).where(User.phone == phone)) is not None:
        raise ReviewerError(
            "that phone already has an account; this script only creates, so a real person's "
            "number can never become a reviewer account by it"
        )
    codes = list(NOS_CODES)
    skills = (await db.scalars(select(Skill).where(Skill.nos_code.in_(codes)))).all()
    if not apply:
        return Outcome(created=False, phone=phone, skills=len(skills))

    user = await provision_candidate(db, phone, get_settings().privacy_notice_version)
    await update_profile(
        db,
        user,
        full_name=NAME,
        headline=HEADLINE,
        location_state=STATE,
        location_district=DISTRICT,
        years_experience=2,
    )
    if skills:
        await add_skills_bulk(db, user.id, [(s.slug, 3) for s in skills], "General Duty Assistant")
    await db.commit()
    return Outcome(created=True, phone=phone, skills=len(skills))


async def _run(args: argparse.Namespace) -> int:
    configure_logging()
    try:
        async with get_sessionmaker()() as db:
            outcome = await create_reviewer(db, args.phone, apply=args.apply, attest=args.attest)
    except ReviewerError as error:
        print(f"Nothing written: {error}", file=sys.stderr)
        return 1
    finally:
        await dispose_engine()
    verb = "Created" if outcome.created else "DRY RUN -- would create"
    print(
        f"{verb} a reviewer account for {outcome.phone} with {outcome.skills} declared standards."
    )
    if not outcome.created:
        print("Re-run with --apply --attest to write.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phone", required=True, help="the reviewer's phone, as in REVIEWER_PHONES"
    )
    parser.add_argument("--apply", action="store_true", help="write; otherwise a dry run")
    parser.add_argument(
        "--attest", action="store_true", help="the privacy notice was shown to this account's user"
    )
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
