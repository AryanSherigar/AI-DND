"""Upload domain exception classes."""

from app.exceptions.base import BaseAppException


class UploadValidationError(BaseAppException):
    """Raised when an uploaded file fails content-type or size validation."""

    def __init__(self, message: str = "Invalid file upload"):
        super().__init__(message=message, status_code=400)


class UploadFailedError(BaseAppException):
    """Raised when the upload to the storage backend fails."""

    def __init__(self, message: str = "File upload failed"):
        super().__init__(message=message, status_code=502)
