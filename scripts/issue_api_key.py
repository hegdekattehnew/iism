"""Issue or revoke an external system's API key (Sprint 33, BL-7.2).

**The raw key exists for one moment: this print.** It is hashed the same way
an OTP or a refresh token is (`hash_secret`, HMAC on `JWT_SECRET_KEY`) before
it ever reaches the database, so a leaked dump is not itself a working
credential -- and there is no "show key again" command, because there is
nothing left to show.

Revoking sets `revoked_at` rather than deleting the row, for the reason
`ServiceAccount`'s own docstring gives: a log line's `service_account_id`
should still resolve to something, long after the key stopped working.

Dry run by default:

    .venv/bin/python scripts/issue_api_key.py acme-hr-integration             # would issue
    .venv/bin/python scripts/issue_api_key.py acme-hr-integration --apply     # issues it
    .venv/bin/python scripts/issue_api_key.py acme-hr-integration --revoke --apply
"""

import argparse
import asyncio
import secrets
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import dispose_engine, get_sessionmaker
from api.core.logging import configure_logging
from api.core.security import hash_secret
from api.modules.identity.models import ServiceAccount


async def _find(db: AsyncSession, name: str) -> ServiceAccount | None:
    return await db.scalar(select(ServiceAccount).where(ServiceAccount.name == name))


async def _run(name: str, *, revoke: bool, apply: bool) -> int:
    configure_logging()
    async with get_sessionmaker()() as db:
        existing = await _find(db, name)

        if revoke:
            if existing is None:
                print(f"No service account named {name!r}.", file=sys.stderr)
                return 1
            if not existing.is_active:
                print(f"{name!r} is already revoked.")
                return 0
            if not apply:
                print(f"DRY RUN. Would revoke: {name!r}")
                print("\nRe-run with --apply to write.")
                return 0
            existing.revoked_at = datetime.now(UTC)
            await db.commit()
            print(f"Revoked: {name!r}")
            return 0

        if existing is not None and existing.is_active:
            print(f"{name!r} already has an active key. Revoke it first to issue a new one.")
            return 1

        if not apply:
            print(f"DRY RUN. Would issue a new key for: {name!r}")
            print("\nRe-run with --apply to write.")
            return 0

        raw_key = secrets.token_urlsafe(32)
        account = ServiceAccount(name=name, hashed_key=hash_secret(raw_key))
        db.add(account)
        await db.commit()
        print(f"Issued for {name!r}. This is the only time the key is shown:\n")
        print(f"  {raw_key}\n")
        print("Send it to the partner over a channel this platform does not log.")
    await dispose_engine()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="a short label for the partner, e.g. acme-hr-integration")
    parser.add_argument("--revoke", action="store_true", help="revoke the existing key instead")
    parser.add_argument("--apply", action="store_true", help="write; otherwise this is a dry run")
    args = parser.parse_args()
    return asyncio.run(_run(args.name, revoke=args.revoke, apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
