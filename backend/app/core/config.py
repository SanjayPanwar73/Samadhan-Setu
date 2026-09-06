from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Use sqlite by default so the project runs with zero external setup.
    # Swap to a postgres URL in .env for production:
    # postgresql://user:password@localhost:5432/complaints_db
    DATABASE_URL: str = "sqlite:///./complaints.db"

    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # How often (minutes) the escalation background job runs
    ESCALATION_CHECK_INTERVAL_MINUTES: int = 10

    # Default SLA window (hours) applied to newly created complaints
    DEFAULT_SLA_HOURS: int = 72

    # Frontend origins allowed to call this API (comma-separated in .env).
    # Explicit origins are retained for production deployments. Local
    # localhost/127.0.0.1 ports are also accepted by the middleware regex.
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
