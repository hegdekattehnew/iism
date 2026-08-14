from fastapi import FastAPI

from app.config import settings
from app.modules.identity.admin_routes import router as admin_router
from app.modules.identity.candidates_routes import router as candidates_router
from app.modules.identity.routes import router as identity_router
from app.modules.identity.tenants_routes import router as tenants_router

app = FastAPI(title="Intelligent Integrated Skill Marketplace", version="0.1.0")

app.include_router(identity_router)
app.include_router(admin_router)
app.include_router(candidates_router)
app.include_router(tenants_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
