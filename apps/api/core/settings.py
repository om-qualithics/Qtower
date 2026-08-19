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
    db_pool_size: int = 5
    db_max_overflow: int = 10
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "misty-admin"
    minio_root_password: str = "changeme-too"
    minio_bucket: str = "misty"

    jwt_signing_key: str = "dev-only-change-me"
    public_hostname: str = "localhost"
    api_public_url: str = "http://localhost:8000"
    web_public_url: str = "http://localhost:3000"

    # "mock" (default, no external calls) or "live" (routes through LiteLLM
    # to whichever real vendor ai_model names).
    ai_provider: str = "mock"
    # LiteLLM model string, e.g. "anthropic/claude-sonnet-5", "openai/gpt-4o",
    # "gemini/gemini-2.0-flash" - the prefix selects the vendor SDK LiteLLM
    # calls under the hood. Swapping vendors is just changing this string
    # plus ai_api_key, no code change.
    ai_model: str = "anthropic/claude-sonnet-5"
    ai_api_key: str = ""

    jackson_base_url: str = "http://localhost:5225"
    jackson_api_keys: str = ""
    jackson_webhook_secret: str = ""

    license_public_key: str = ""
    license_token: str = ""

    # "mock" (default, no real SMTP call - logs to notification_log only) or
    # "live" (sends via smtplib once smtp_host/smtp_from_address are set).
    # Same shape as ai_provider/ai_model above.
    notifications_provider: str = "mock"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""

    @property
    def license_public_key_pem(self) -> str:
        if not self.license_public_key:
            return ""
        return base64.b64decode(self.license_public_key).decode()


settings = Settings()
