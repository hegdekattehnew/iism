from fastapi import FastAPI

from app.config import settings
from app.modules.identity.routes import router as identity_router

app = FastAPI(title="Intelligent Integrated Skill Marketplace", version="0.1.0")

app.include_router(identity_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
