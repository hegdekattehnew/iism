from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import User
from app.modules.identity.schemas import BulkUploadError, BulkUploadResult
from app.modules.identity.service import (
    _create_tenant_with_owner,
    _get_user_by_email,
    request_account_claim,
)

MAX_BULK_ROWS = 500


async def bulk_create_candidates(
    db: AsyncSession, records: list[tuple[str, str]]
) -> BulkUploadResult:
    if len(records) > MAX_BULK_ROWS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot process more than {MAX_BULK_ROWS} rows"
        )

    created_users: list[User] = []
    skipped: list[BulkUploadError] = []

    for row_number, (email, full_name) in enumerate(records, start=1):
        email = email.strip()
        full_name = full_name.strip()
        if not email or not full_name:
            skipped.append(
                BulkUploadError(
                    row=row_number, email=email or None, reason="Missing email or full name"
                )
            )
            continue
        if await _get_user_by_email(db, email) is not None:
            skipped.append(
                BulkUploadError(row=row_number, email=email, reason="Email already registered")
            )
            continue

        user = User(email=email, full_name=full_name, hashed_password=None)
        db.add(user)
        await db.flush()
        await _create_tenant_with_owner(db, user, f"{full_name}'s workspace", "personal")
        created_users.append(user)

    await db.commit()
    for user in created_users:
        await request_account_claim(user)

    return BulkUploadResult(created=len(created_users), skipped=skipped)
