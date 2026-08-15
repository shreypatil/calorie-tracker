"""Choosing a provider.

`auto` — the default — uses the real adapter when a key is configured and the
stub otherwise. That is what lets a fresh clone run every AI feature with no
credentials while a configured deployment gets real inference, from the same
code path.
"""

from functools import lru_cache

from app.ai.provider import AIProvider
from app.ai.stub import StubProvider
from app.core.config import Settings, get_settings
from app.core.logging import logger


def build_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "stub":
        return StubProvider()

    if settings.ai_provider == "auto" and not settings.has_ai_credentials:
        logger.info("ai_provider_selected", extra={"provider": "stub", "reason": "no_api_key"})
        return StubProvider()

    # Imported lazily so the optional `openai` package is only needed when a
    # real provider is actually configured.
    from app.ai.openai_compatible import OpenAICompatibleProvider

    logger.info(
        "ai_provider_selected",
        extra={"provider": "openai_compatible", "model": settings.ai_model},
    )
    return OpenAICompatibleProvider(settings)


@lru_cache
def get_provider() -> AIProvider:
    """Cached for the process — building a client per request is wasteful."""
    return build_provider(get_settings())
