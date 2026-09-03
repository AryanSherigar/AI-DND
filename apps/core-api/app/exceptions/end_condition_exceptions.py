"""EndCondition domain exception classes."""

from app.exceptions.base import BaseAppException


class EndConditionNotFoundError(BaseAppException):
    """Raised when an end condition is not found or not owned by the scenario."""

    def __init__(self, message: str = "End condition not found"):
        super().__init__(message=message, status_code=404)


class EndConditionValidationError(BaseAppException):
    """Raised when an end condition's expression references an unknown field."""

    def __init__(self, message: str = "Invalid end condition configuration"):
        super().__init__(message=message, status_code=422)
