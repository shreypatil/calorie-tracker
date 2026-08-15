"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.routers import ai, auth, chat, entries, goals, imports, reports

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(goals.router)
api_router.include_router(entries.router)
api_router.include_router(reports.router)
api_router.include_router(imports.router)
api_router.include_router(chat.router)
api_router.include_router(ai.router)

__all__ = ["api_router"]
