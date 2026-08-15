"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.routers import auth, entries, goals, reports

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(goals.router)
api_router.include_router(entries.router)
api_router.include_router(reports.router)

__all__ = ["api_router"]
