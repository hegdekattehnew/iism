"""Grant or revoke operator authority (ADR-042).

**This is the only writer of `users.is_staff` in the entire product**, and
deliberately not an endpoint. Running it needs `DATABASE_URL` and network
access to Postgres -- a capability strictly greater than anything the API
grants anybody -- so it lowers no bar: whoever can run this can already
`UPDATE users SET is_staff = true` by hand. What it adds is that the act is
legible, refuses the dangerous shapes, and says who else holds the flag.

A back office whose first feature is its own escalation path is the failure
ADR-042 exists to prevent, so there is no "manage operators" route and there
will not be one.

**It never creates an account.** A script that can mint a user *and* make them
staff is a one-command account takeover, so an unknown address is an error and
nothing is written.

Revoking uses the same script, so a compromised operator is closed out by
somebody with database access rather than by another operator -- and the last
operator can be removed without needing an interface that would have to let
them.

Dry run by default:

    .venv/bin/python scripts/grant_staff.py ops@example.com             # says what would happen
    .venv/bin/python scripts/grant_staff.py ops@example.com --apply     # does it
    .venv/bin/python scripts/grant_staff.py ops@example.com --revoke --apply
"""

import argparse
import asyncio
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import dispose_engine, get_sessionmaker
from api.core.logging import configure_logging
from api.modules.identity.models import User
from api.modules.operations import set_staff, staff_roster


def _label(user: User) -> str:
    """Enough to recognise the account, and the id it is actually keyed on."""
    return f"{user.full_name or '(no name)'} · {user.email or user.phone} · {user.id}"


async def _find(db: AsyncSession, address: str) -> User | None:
    key = address.strip().lower()
    user = await db.scalar(select(User).where(func.lower(User.email) == key))
    if user is None:
        user = await db.scalar(select(User).where(User.phone == address.strip()))
    return user


async def _run(address: str, *, revoke: bool, apply: bool) -> int:
    configure_logging()
    verb = "Revoke from" if revoke else "Grant to"
    async with get_sessionmaker()() as db:
        user = await _find(db, address)
        if user is None:
            print(f"No account for {address!r}.", file=sys.stderr)
            print("This never creates one — ask them to sign up first.", file=sys.stderr)
            return 1

        if user.is_staff == (not revoke):
            print(f"Already {'not ' if revoke else ''}an operator: {_label(user)}")
        elif not apply:
            print("DRY RUN. Would change:")
            print(f"  {verb}: {_label(user)}")
            print("\nRe-run with --apply to write.")
        else:
            await set_staff(db, address=address, staff=not revoke)
            print(f"{'Revoked from' if revoke else 'Granted to'}: {_label(user)}")

        # Printed every run, including the dry one. "Who else is staff" is the
        # question worth answering at the moment you add one, and nothing else
        # in the product answers it.
        roster = await staff_roster(db)
        print(f"\nOperators now ({len(roster)}):")
        for member in sorted(roster, key=lambda u: str(u.email or u.phone)):
            print(f"  {_label(member)}")
        if not roster:
            print("  (nobody — the back office is unreachable)")
    await dispose_engine()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address", help="the email or phone of an account that already exists")
    parser.add_argument("--revoke", action="store_true", help="take operator authority away")
    parser.add_argument("--apply", action="store_true", help="write; otherwise this is a dry run")
    args = parser.parse_args()
    return asyncio.run(_run(args.address, revoke=args.revoke, apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
