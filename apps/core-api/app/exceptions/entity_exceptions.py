"""Entity domain exception classes."""

from app.exceptions.base import BaseAppException


class EntityNotFoundError(BaseAppException):
    """Raised when an entity is not found or does not belong to the scenario."""

    def __init__(self, message: str = "Entity not found"):
        super().__init__(message=message, status_code=404)


class EntityValidationError(BaseAppException):
    """Raised when entity fields fail domain validation."""

    def __init__(self, message: str = "Invalid entity configuration"):
        super().__init__(message=message, status_code=422)
