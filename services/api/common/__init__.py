"""
Common API Package.
Contains shared exception definitions, dependency utilities, and response schemas.
"""
from services.api.common.exceptions import (
    APIException,
    AccessDeniedException,
    ResourceNotFoundException,
    ServiceUnavailableException,
)
from services.api.common.responses import APIResponse, ErrorResponse

__all__ = [
    "APIException",
    "AccessDeniedException",
    "ResourceNotFoundException",
    "ServiceUnavailableException",
    "APIResponse",
    "ErrorResponse",
]
