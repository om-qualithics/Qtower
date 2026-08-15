from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / "infra" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://misty_app:changeme-app@localhost:5432/misty"
    migrations_database_url: str = "postgresql+psycopg://misty:changeme@localhost:5432/misty"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "misty-admin"
    minio_root_password: str = "changeme-too"
    minio_bucket: str = "misty"

    jwt_signing_key: str = "dev-only-change-me"
    public_hostname: str = "localhost"

    ai_provider: str = "mock"
    anthropic_api_key: str = ""


settings = Settings()
