"""Bootstrap the first Super Admin. Run manually: python scripts/create_superuser.py

Not exposed via the API — /admin/staff requires an existing super_admin, so the
very first one has to be created directly against the database.
"""

import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.modules.identity.models import User  # noqa: E402


async def main() -> None:
    email = input("Email: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return

    async with async_session_factory() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            print(f"A user with email {email} already exists.")
            return

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            platform_role="super_admin",
            is_email_verified=True,
        )
        db.add(user)
        await db.commit()
        print(f"Created super admin {email}.")


if __name__ == "__main__":
    asyncio.run(main())
