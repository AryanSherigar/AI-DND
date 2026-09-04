"""Scenario entity type template domain exception classes."""

from app.exceptions.base import BaseAppException


class ScenarioEntityTypeNotFoundError(BaseAppException):
    """Raised when a custom entity type template is not found or does not
    belong to the scenario."""

    def __init__(self, message: str = "Entity type not found"):
        super().__init__(message=message, status_code=404)


class ScenarioEntityTypeValidationError(BaseAppException):
    """Raised when a custom entity type template fails domain validation
    (e.g. duplicate key, key collides with a built-in type)."""

    def __init__(self, message: str = "Invalid entity type configuration"):
        super().__init__(message=message, status_code=422)


class ScenarioEntityTypeInUseError(BaseAppException):
    """Raised when deleting a custom entity type template still referenced by
    at least one entity."""

    def __init__(self, message: str = "Entity type is still in use"):
        super().__init__(message=message, status_code=409)
