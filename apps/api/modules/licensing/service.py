import logging
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException

from apps.api.core.settings import settings
from apps.api.modules.branding import service as branding_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.licensing.schemas import LicensePayload

logger = logging.getLogger(__name__)

ALGORITHM = "RS256"


def validate_license(token: str) -> LicensePayload | None:
    """Pure, local signature + expiry check - no network calls, per
    handoff's "no phone-home" requirement. Returns None on any failure
    (bad signature, expired, malformed) rather than raising, since callers
    treat "invalid" and "absent" the same way.
    """
    if not token or not settings.license_public_key_pem:
        return None
    try:
        claims = jwt.decode(token, settings.license_public_key_pem, algorithms=[ALGORITHM])
        payload = LicensePayload(**claims)
    except jwt.PyJWTError:
        return None

    # expires_at is our own claim, not the JWT-reserved "exp" - PyJWT's
    # built-in expiry check does not apply to it, so it's checked explicitly.
    if payload.expires_at < datetime.now(timezone.utc):
        return None
    return payload


def sync_license_on_boot() -> None:
    """Called once from the FastAPI startup hook. Never raises - an
    invalid/missing license degrades the deployment (feature routes behind
    require_valid_license start 402ing) rather than crash-looping the
    container, since that's a worse failure mode for a customer than a
    clear in-app error.
    """
    try:
        org = identity_service.get_org()
    except RuntimeError:
        logger.warning("License sync skipped: no org configured yet (run seed_org.py)")
        return

    payload = validate_license(settings.license_token)
    validated_at = datetime.now(timezone.utc)

    if payload is None:
        branding_service.upsert_license_result(
            org,
            valid=False,
            token=settings.license_token,
            seat_count=None,
            expires_at=None,
            enabled_modules=None,
            validated_at=validated_at,
        )
        logger.warning("License invalid or missing - feature routes will return 402")
        return

    branding_service.upsert_license_result(
        org,
        valid=True,
        token=settings.license_token,
        seat_count=payload.seat_count,
        expires_at=payload.expires_at,
        enabled_modules=payload.enabled_modules,
        validated_at=validated_at,
    )
    logger.info("License valid: %s seats, expires %s", payload.seat_count, payload.expires_at)


def require_valid_license() -> None:
    """FastAPI dependency for gating feature routes. Deliberately not
    applied to /health, so container orchestration health checks keep
    passing regardless of license state.
    """
    org = identity_service.get_org()
    config = branding_service.get_config(org)
    if config is None or not config.license_valid:
        raise HTTPException(status_code=402, detail="No valid license for this deployment")
