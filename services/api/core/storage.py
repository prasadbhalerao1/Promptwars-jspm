"""File storage — Cloudinary only, per .agents/decisions.md (no other provider)."""

from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader

from services.api.core.config import get_settings

_configured = False


class StorageUnavailable(RuntimeError):
    """Raised when CLOUDINARY_URL isn't configured with real credentials."""


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return

    settings = get_settings()
    parsed = urlparse(settings.cloudinary_url)
    if not parsed.username or not parsed.password or not parsed.hostname:
        raise StorageUnavailable("CLOUDINARY_URL is not configured with real credentials.")

    cloudinary.config(cloud_name=parsed.hostname, api_key=parsed.username, api_secret=parsed.password)
    _configured = True


def upload_file(file_bytes: bytes, public_id: str, resource_type: str = "auto") -> tuple[str, str]:
    """Returns (public_url, storage_key)."""
    _ensure_configured()
    result = cloudinary.uploader.upload(file_bytes, public_id=public_id, resource_type=resource_type)
    return result["secure_url"], result["public_id"]
