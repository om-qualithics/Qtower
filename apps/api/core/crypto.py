from cryptography.fernet import Fernet

from apps.api.core.settings import settings


class EncryptionNotConfiguredError(Exception):
    pass


def encrypt_secret(plaintext: str) -> str:
    """Encrypts a secret for storage at rest - first use of this pattern
    anywhere in this codebase (every other secret so far is either signed,
    not encrypted, e.g. the license token, or never stored by us at all,
    e.g. Jackson's SAML secrets). Used for a GitHub App's private key
    (codescan/service.py) - fails loud if ENCRYPTION_KEY isn't configured,
    same "fail loud, don't silently downgrade" rule this codebase already
    follows for AiGatewayConfigError/NotificationConfigError."""
    if not settings.encryption_key:
        raise EncryptionNotConfiguredError("ENCRYPTION_KEY is not configured - run infra/scripts/gen-encryption-key.sh")
    return Fernet(settings.encryption_key.encode()).encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    if not settings.encryption_key:
        raise EncryptionNotConfiguredError("ENCRYPTION_KEY is not configured - run infra/scripts/gen-encryption-key.sh")
    return Fernet(settings.encryption_key.encode()).decrypt(ciphertext.encode()).decode()
