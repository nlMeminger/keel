from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App-wide configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://keel:keel@localhost:5432/keel"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/2"
    celery_result_backend: str = "redis://localhost:6379/3"

    jwt_signing_key: str = "dev-only-insecure-key-change-me-32-bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    refresh_token_absolute_expire_days: int = 90

    encryption_key: str = "dev-only-insecure-key-change-me-32bytes!"

    cors_origins: list[str] = ["http://localhost:5173"]

    environment: str = "development"


settings = Settings()
