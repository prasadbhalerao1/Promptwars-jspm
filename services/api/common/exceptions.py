"""
Common API Exceptions.
Defines domain-agnostic exception classes and error contracts for FastAPI exception handlers.
"""

class APIException(Exception):
    """Base exception for all domain API errors."""
    def __init__(self, message: str, status_code: int = 400, detail: str | dict | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(message)


class ServiceUnavailableException(APIException):
    """Raised when an external AI service or database dependency is unreachable."""
    def __init__(self, service_name: str, reason: str = "Service temporary unreachable"):
        super().__init__(
            message=f"{service_name} unavailable: {reason}",
            status_code=503,
            detail=f"{service_name}_unavailable",
        )


class ResourceNotFoundException(APIException):
    """Raised when a requested DB entity does not exist."""
    def __init__(self, resource_name: str, resource_id: str | None = None):
        detail_msg = f"{resource_name}_not_found" if not resource_id else f"{resource_name}_{resource_id}_not_found"
        super().__init__(
            message=f"{resource_name} not found.",
            status_code=404,
            detail=detail_msg,
        )


class AccessDeniedException(APIException):
    """Raised when RBAC or resource ownership validation fails."""
    def __init__(self, reason: str = "Forbidden"):
        super().__init__(
            message="Access denied.",
            status_code=403,
            detail=reason,
        )
