"""
Third-Party Integrations Package.
Modular wrappers for Auth, Storage (Cloudinary/S3), Qdrant, and Redis.
"""
from services.api.core.rbac import get_current_user, require_role
from services.api.integrations.qdrant.qdrant_client import QdrantUnavailable, get_qdrant_client
from services.api.integrations.storage.cloudinary_adapter import StorageUnavailable, upload_file

__all__ = [
    "get_current_user",
    "require_role",
    "StorageUnavailable",
    "upload_file",
    "QdrantUnavailable",
    "get_qdrant_client",
]
