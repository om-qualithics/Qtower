"""Shared logo upload validation + storage-key convention for Milestone 17
(AI Tools + Vendor Register logos) - one place so tools/ and vendors/
don't each define their own allow-list/size-cap logic."""

LOGO_MAX_SIZE_BYTES = 512 * 1024

_ALLOWED_LOGO_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/svg+xml"}


class LogoValidationError(Exception):
    pass


def validate_logo_upload(content_type: str | None, data: bytes) -> str:
    """Returns the validated (lowercased) content type or raises
    LogoValidationError - the caller uses the returned value as the
    Content-Type MinIO stores the object under, so a later GET can hand
    it straight back without re-deriving it from a filename extension."""
    normalized = (content_type or "").lower()
    if normalized not in _ALLOWED_LOGO_CONTENT_TYPES:
        raise LogoValidationError("Unsupported logo type - allowed: PNG, JPEG, SVG")
    if len(data) > LOGO_MAX_SIZE_BYTES:
        raise LogoValidationError(f"Logo exceeds the {LOGO_MAX_SIZE_BYTES // 1024}KB size limit")
    return normalized


def logo_storage_key(entity_type: str, org_id: str, entity_id: str) -> str:
    # No extension in the key - the Content-Type header (set at upload,
    # read back at download via storage.download_bytes_with_content_type())
    # is what tells a consumer what it is, not the key itself. A re-upload
    # to the same entity overwrites in place rather than orphaning the old
    # object under a different extension.
    return f"logos/{org_id}/{entity_type}/{entity_id}"
