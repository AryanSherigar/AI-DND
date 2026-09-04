"""User domain exceptions."""

from app.exceptions.base import BaseAppException


class UserNotFoundError(BaseAppException):
    """Raised when a user is not found by ID."""

    def __init__(self, message: str = "User not found") -> None:
        super().__init__(message, status_code=404)


class InvalidProfileDataError(BaseAppException):
    """Raised when profile update fields fail validation."""

    def __init__(self, message: str = "Invalid profile data") -> None:
        super().__init__(message, status_code=422)
