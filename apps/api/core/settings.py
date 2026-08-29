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
    # Only used for *presigned* URLs (policy downloads, escalation
    # attachments, codescan reports) - those get handed to the browser,
    # which is outside the docker network and can't resolve an internal
    # service hostname like "minio". Blank (the default, native dev where
    # there's no such split) falls back to minio_endpoint. When the
    # api/worker run containerized (see infra/docker-compose.yml's
    # `codescan` profile), MINIO_ENDPOINT is the internal `http://minio:9000`
    # for the container's own upload/download calls, while this is set to
    # `http://localhost:9000` (reachable via the exposed port mapping) so
    # generated download links actually work in the browser.
    minio_public_endpoint: str = ""
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

    # Break-glass local login, independent of Jackson/SAML entirely - lets
    # a deployment operator always get in (to fix a broken SSO connection,
    # or to bootstrap the very first real admin under an IdP that can't
    # push role data, e.g. Google Workspace) regardless of IdP state. Unset
    # by default = this login path is disabled outright, not a silent
    # blank-password backdoor. Set via apps/api/scripts/set_super_admin_password.py,
    # never plaintext.
    #
    # Stored base64-encoded (like license_public_key below), NOT as the
    # raw bcrypt hash string - a bcrypt hash always contains literal `$`
    # characters (its own format is `$2b$12$salt+hash`), and Docker
    # Compose's env_file loading interpolates `$word` sequences as
    # `${word}` variable references, silently corrupting the value when
    # it's passed into a container this way (confirmed: this broke
    # super-admin login the first time the api/worker services were
    # containerized, Milestone 13). Base64 has no `$` characters, so it
    # survives that interpolation pass untouched either way.
    super_admin_email: str = ""
    super_admin_password_hash_b64: str = ""

    license_public_key: str = ""
    license_token: str = ""

    # Fernet key (core/crypto.py) - encrypts secrets at rest, currently
    # only a GitHub App's private key (modules/codescan). Generate via
    # infra/scripts/gen-encryption-key.sh. Blank = encrypt/decrypt_secret
    # raise instead of silently no-op'ing.
    encryption_key: str = ""

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

    @property
    def super_admin_password_hash(self) -> str:
        if not self.super_admin_password_hash_b64:
            return ""
        return base64.b64decode(self.super_admin_password_hash_b64).decode()


settings = Settings()
