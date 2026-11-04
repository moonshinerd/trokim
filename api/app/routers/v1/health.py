from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def get_health():
    return {
        "status": "healthy",
        "service": "trokim-api",
        "environment": settings.ENVIRONMENT,
        "database": "sqlite_local",
    }
