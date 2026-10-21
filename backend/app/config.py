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

    # Plaid sandbox credentials (https://dashboard.plaid.com/team/keys) — blank by default so
    # a dev environment without them still boots; routes that need Plaid fail per-call, not
    # at startup.
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"
    # Destination for Plaid's inbound webhooks (API_SPEC.md §17) — must be a publicly
    # reachable HTTPS URL in real sandbox testing (e.g. via ngrok in local dev).
    plaid_webhook_url: str = ""


settings = Settings()
