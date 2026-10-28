"""
Cloudinary & S3 Storage Integration Adapter.
Provides uniform upload/delete operations for documents, photos, and resumes.
"""
from services.api.core.storage import StorageUnavailable, upload_file

__all__ = ["StorageUnavailable", "upload_file"]
