from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-only-change-me"

# Repo root, so the backend reads the same .env docker-compose does regardless of
# CWD. Assumes this file stays at backend/app/core/, three levels down.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    postgres_user: str = "gabai"
    postgres_password: str = "gabai"
    postgres_db: str = "gabai"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    secret_key: str = "dev-only-change-me"
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"

    confidence_threshold: float = 0.70

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def reject_default_secret_outside_development(self) -> "Settings":
        # secret_key signs the session cookie. Shipping the published default
        # means anyone can forge a session, so fail at boot rather than serve.
        if self.environment != "development" and self.secret_key == DEFAULT_SECRET:
            raise ValueError(
                "SECRET_KEY is still the default. Set a real value: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
