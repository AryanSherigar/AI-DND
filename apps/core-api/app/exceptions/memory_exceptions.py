"""Memory-layer integration exception classes."""

from app.exceptions.base import BaseAppException


class MemoryLayerUnavailableError(BaseAppException):
    """Raised when the memory layer is transiently unavailable (timeout, 5xx,
    connection error, or an unexpected client error)."""

    def __init__(self, message: str = "Memory layer is temporarily unavailable"):
        super().__init__(message=message, status_code=502)


class MemoryBatchNotFoundError(BaseAppException):
    """Raised when a batch_id is unknown to the memory layer."""

    def __init__(self, message: str = "Memory batch not found"):
        super().__init__(message=message, status_code=404)
