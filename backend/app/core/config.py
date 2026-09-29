from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
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

    # Chosen on the validation split from the fine-tuned model's confidences
    # (ml/scripts/evaluate_deployed.py): about a quarter of requests go to review
    # and 92% of the rest reach the right category's handler.
    confidence_threshold: float = 0.70

    # Email through Resend. Empty key means nothing is sent, see app/mail.py.
    resend_api_key: str = ""
    mail_from: str = "GABAI <no-reply@gabai.help>"
    # Where emailed links point. The site, not the API.
    public_url: str = "http://localhost:5173"
    # Staff can only approve a sign-up whose email is confirmed. Turn off only
    # while email isn't set up yet, or nobody new can ever be approved.
    require_verified_email: bool = True

    # Where the exported ONNX models live. Relative paths resolve from backend/.
    # Missing is fine: requests go to manual review instead.
    model_dir: str = "models"

    # Retention, read by `python -m app.retention` only. Unset means that step
    # never runs, so nothing is removed until the barangay picks a period.
    # Days after a request is resolved or closed before its text, notes and
    # attachments are removed.
    retention_request_days: int | None = None
    # Days after a citizen account is deactivated or rejected before its name,
    # email and residence are removed.
    retention_account_days: int | None = None
    # Days before an audit entry's IP address is cleared.
    retention_ip_days: int | None = None

    # Read by `python -m app.seed` only. A fresh database has no admin and no way
    # to make one through the API, so the first one comes from here.
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_admin_name: str = "Administrator"

    # Demo seats for evaluation week. Off by default because the repo is public
    # and these accounts are documented in the README.
    seed_demo: bool = False
    seed_demo_password: str | None = None

    @field_validator(
        "retention_request_days", "retention_account_days", "retention_ip_days", mode="before"
    )
    @classmethod
    def empty_means_unset(cls, value):
        # .env.example ships these as `RETENTION_REQUEST_DAYS=`, which arrives as
        # "" and isn't an int.
        return None if value == "" else value

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
