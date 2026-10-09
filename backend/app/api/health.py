from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "desktop": settings.desktop_mode,
    }
