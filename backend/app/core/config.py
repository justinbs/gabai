from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root, so the backend reads the same .env docker-compose does regardless of CWD.
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
