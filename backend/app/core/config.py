"""Application configuration loaded from environment variables (12-factor style)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "change-me-insecure-development-secret-key-000000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Multi-Cloud Management Platform"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # PostgreSQL is the only supported database.
    database_url: str = "postgresql+psycopg://mcmp:mcmp@localhost:5432/mcmp"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    # When true, Celery tasks execute in-process (no broker/worker needed). Used for tests
    # and for local development without Redis.
    celery_task_always_eager: bool = True
    sync_interval_minutes: int = 60

    # Auth
    jwt_secret_key: str = _INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    allow_self_registration: bool = True

    # Comma-separated Fernet keys. The first key encrypts, all keys decrypt (key rotation).
    credentials_encryption_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Cloud adapters: "mock" (default) uses simulated providers, "real" uses the cloud SDKs.
    cloud_provider_mode: Literal["mock", "real"] = "mock"

    # Terraform
    terraform_binary: str = "terraform"
    terraform_workdir: str = ".terraform-runs"
    # "auto": run the terraform binary when present AND cloud_provider_mode == "real";
    # otherwise produce a clearly-labelled mock plan. "mock": always mock.
    terraform_mode: Literal["auto", "mock"] = "auto"
    # Real `terraform apply` is disabled unless explicitly enabled (still needs confirmation).
    terraform_apply_enabled: bool = False
    provisioning_confirmation_ttl_minutes: int = 30

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @field_validator("cors_origins", "credentials_encryption_keys", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _check_production_secrets(self) -> Settings:
        if self.environment == "production":
            if self.jwt_secret_key == _INSECURE_DEFAULT_SECRET or len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be set to a strong value in production")
            if not self.credentials_encryption_keys:
                raise ValueError("CREDENTIALS_ENCRYPTION_KEYS must be set in production")
        if not self.database_url.startswith("postgresql"):
            raise ValueError("Only PostgreSQL DATABASE_URLs are supported")
        return self

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
