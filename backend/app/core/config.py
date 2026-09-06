import secrets
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # SQLite keeps the local demo self-contained. Production must provide a
    # managed database URL and disable automatic schema creation.
    DATABASE_URL: str = "sqlite:///./complaints.db"

    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    AUTO_CREATE_SCHEMA: bool = True

    ESCALATION_CHECK_INTERVAL_MINUTES: int = 10
    # An overdue complaint may be escalated again only after this interval.
    ESCALATION_REPEAT_HOURS: int = 24
    DEFAULT_SLA_HOURS: int = 72

    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_security_settings(self):
        unsafe_values = {
            "",
            "change-this-secret-key-in-production",
            "change-this-to-a-long-random-string-in-production",
        }
        if not self.SECRET_KEY or self.SECRET_KEY.lower() in unsafe_values:
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "SECRET_KEY must be explicitly configured with a strong random value in production"
                )
            # Local demos remain zero-configuration, but never use a known
            # placeholder. Tokens are intentionally invalidated on restart.
            self.SECRET_KEY = secrets.token_urlsafe(32)
        elif self.ENVIRONMENT == "production" and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")

        if self.ENVIRONMENT == "production" and self.AUTO_CREATE_SCHEMA:
            raise ValueError(
                "AUTO_CREATE_SCHEMA must be false in production; run Alembic migrations"
            )
        if self.ENVIRONMENT == "production" and self.DATABASE_URL.startswith("sqlite"):
            raise ValueError("Production must use a managed database, not SQLite")
        if self.ENVIRONMENT == "production" and any(
            "localhost" in origin or "127.0.0.1" in origin
            for origin in self.CORS_ORIGINS
        ):
            raise ValueError("Production CORS_ORIGINS must not include localhost")
        if self.ESCALATION_CHECK_INTERVAL_MINUTES < 1:
            raise ValueError("ESCALATION_CHECK_INTERVAL_MINUTES must be at least 1")
        if self.ESCALATION_REPEAT_HOURS < 1:
            raise ValueError("ESCALATION_REPEAT_HOURS must be at least 1")
        if self.ACCESS_TOKEN_EXPIRE_MINUTES < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 1")
        if self.DEFAULT_SLA_HOURS < 1:
            raise ValueError("DEFAULT_SLA_HOURS must be at least 1")
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
