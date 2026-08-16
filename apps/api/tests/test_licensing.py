from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api.modules.licensing.schemas import LicensePayload
from apps.api.modules.licensing.service import validate_license


def _patch_public_key(monkeypatch, public_key_pem: str) -> None:
    # settings is a pydantic BaseSettings instance - license_public_key_pem
    # is a read-only property, so patch the whole module-level `settings`
    # name with a lightweight stand-in instead of trying to set an
    # attribute pydantic won't allow.
    monkeypatch.setattr(
        "apps.api.modules.licensing.service.settings",
        SimpleNamespace(license_public_key_pem=public_key_pem),
    )


def _generate_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _make_token(private_key: str, **overrides) -> str:
    payload = {
        "org_name": "Test Org",
        "seat_count": 10,
        "issued_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2027-01-01T00:00:00+00:00",
        "enabled_modules": ["policy"],
        **overrides,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_valid_license_is_accepted(monkeypatch) -> None:
    private_key, public_key = _generate_keypair()
    _patch_public_key(monkeypatch, public_key)
    token = _make_token(private_key)

    result = validate_license(token)

    assert isinstance(result, LicensePayload)
    assert result.org_name == "Test Org"
    assert result.seat_count == 10


def test_tampered_signature_is_rejected(monkeypatch) -> None:
    private_key, public_key = _generate_keypair()
    _, wrong_public_key = _generate_keypair()
    _patch_public_key(monkeypatch, wrong_public_key)
    token = _make_token(private_key)

    assert validate_license(token) is None


def test_expired_license_is_rejected(monkeypatch) -> None:
    private_key, public_key = _generate_keypair()
    _patch_public_key(monkeypatch, public_key)
    # expires_at is our own claim, not the JWT-reserved "exp" - PyJWT's
    # built-in expiry check doesn't apply to it, so validate_license must
    # check it explicitly (a prior version of this code didn't, and this
    # test would have caught that).
    token = _make_token(private_key, expires_at="2020-01-01T00:00:00+00:00")

    assert validate_license(token) is None


def test_missing_token_is_rejected(monkeypatch) -> None:
    _, public_key = _generate_keypair()
    _patch_public_key(monkeypatch, public_key)
    assert validate_license("") is None
