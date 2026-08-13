from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="Intelligent Integrated Skill Marketplace", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
