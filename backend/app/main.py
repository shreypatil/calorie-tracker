"""Application factory and middleware wiring."""

import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError, register_exception_handlers
from app.core.logging import configure_logging, logger, set_request_id
from app.services.rate_limit import limiter


class RateLimitedError(AppError):
    status_code = 429
    title = "Too Many Requests"
    error_type = "/errors/rate-limited"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging("DEBUG" if settings.debug else "INFO")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend API for the Personal Calorie Tracker.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        """Tag every request and its logs with a traceable ID."""
        request_id = set_request_id(request.headers.get("X-Request-ID"))
        started = time.perf_counter()

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response

    register_exception_handlers(app)

    @app.exception_handler(RateLimitExceeded)
    async def _handle_rate_limit(request: Request, exc: RateLimitExceeded):
        handler = app.exception_handlers[AppError]
        return await handler(request, RateLimitedError("Too many requests. Slow down."))

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
