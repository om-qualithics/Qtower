import pytest

from apps.api.core.media import LOGO_MAX_SIZE_BYTES, LogoValidationError, logo_storage_key, validate_logo_upload


def test_validate_logo_upload_accepts_allowed_types() -> None:
    assert validate_logo_upload("image/png", b"x") == "image/png"
    assert validate_logo_upload("image/jpeg", b"x") == "image/jpeg"
    assert validate_logo_upload("image/svg+xml", b"x") == "image/svg+xml"


def test_validate_logo_upload_rejects_unsupported_type() -> None:
    with pytest.raises(LogoValidationError):
        validate_logo_upload("application/pdf", b"x")


def test_validate_logo_upload_rejects_missing_content_type() -> None:
    with pytest.raises(LogoValidationError):
        validate_logo_upload(None, b"x")


def test_validate_logo_upload_rejects_oversized_file() -> None:
    with pytest.raises(LogoValidationError):
        validate_logo_upload("image/png", b"x" * (LOGO_MAX_SIZE_BYTES + 1))


def test_logo_storage_key_has_no_extension_and_is_per_entity() -> None:
    key = logo_storage_key("tool", "org-1", "tool-1")
    assert key == "logos/org-1/tool/tool-1"
    assert logo_storage_key("tool", "org-1", "tool-2") != key
