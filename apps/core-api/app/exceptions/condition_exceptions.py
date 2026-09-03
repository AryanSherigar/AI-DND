"""Active condition (ScenarioCondition) domain exception classes."""

from app.exceptions.base import BaseAppException


class ConditionNotFoundError(BaseAppException):
    """Raised when a condition is not found or does not belong to the scenario."""

    def __init__(self, message: str = "Condition not found"):
        super().__init__(message=message, status_code=404)


class ConditionValidationError(BaseAppException):
    """Raised when a condition's expression references a field that doesn't
    exist in the scenario's state_schema or an entity's attributes_schema."""

    def __init__(self, message: str = "Invalid condition configuration"):
        super().__init__(message=message, status_code=422)
