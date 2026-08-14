import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, hash_api_key
from app.modules.identity.models import ServiceAccount


async def create_service_account(
    db: AsyncSession, tenant_id: uuid.UUID, name: str
) -> tuple[ServiceAccount, str]:
    api_key = generate_api_key()
    service_account = ServiceAccount(
        tenant_id=tenant_id, name=name, hashed_key=hash_api_key(api_key)
    )
    db.add(service_account)
    await db.commit()
    await db.refresh(service_account)
    return service_account, api_key
