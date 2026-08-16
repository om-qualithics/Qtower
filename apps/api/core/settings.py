import base64
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
    api_public_url: str = "http://localhost:8000"
    web_public_url: str = "http://localhost:3000"

    ai_provider: str = "mock"
    anthropic_api_key: str = ""

    jackson_base_url: str = "http://localhost:5225"
    jackson_api_keys: str = ""
    jackson_webhook_secret: str = ""

    license_public_key: str = ""
    license_token: str = ""

    @property
    def license_public_key_pem(self) -> str:
        if not self.license_public_key:
            return ""
        return base64.b64decode(self.license_public_key).decode()


settings = Settings()
