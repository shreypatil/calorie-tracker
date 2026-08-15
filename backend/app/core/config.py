"""Application settings, loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Calorie Tracker API"
    api_prefix: str = "/api/v1"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "sqlite:///./data/calorie_tracker.db"

    jwt_secret: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    cors_origins: list[str] = ["http://localhost:5173"]

    default_page_size: int = 25
    max_page_size: int = 100

    ai_provider: Literal["auto", "claude", "openai", "stub"] = "auto"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 50

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> "Settings":
        if (
            self.environment == "production"
            and self.jwt_secret.get_secret_value() == DEFAULT_JWT_SECRET
        ):
            raise ValueError(
                "JWT_SECRET is still the development default. "
                "Set a strong unique value before running in production."
            )
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
