"""Scenario domain exception classes."""

from app.exceptions.base import BaseAppException


class ScenarioNotFoundError(BaseAppException):
    """Raised when a scenario is not found or inaccessible."""

    def __init__(self, message: str = "Scenario not found"):
        super().__init__(message=message, status_code=404)


class ScenarioAccessDeniedError(BaseAppException):
    """Raised when a user is not permitted to access or modify a scenario."""

    def __init__(self, message: str = "Access denied for this scenario"):
        super().__init__(message=message, status_code=403)


class ScenarioValidationError(BaseAppException):
    """Raised when scenario fields or rules fail domain validation."""

    def __init__(self, message: str = "Invalid scenario configuration"):
        super().__init__(message=message, status_code=400)


class ScenarioDeletionError(BaseAppException):
    """Raised when scenario deletion cannot be performed."""

    def __init__(self, message: str = "Cannot delete scenario"):
        super().__init__(message=message, status_code=409)
