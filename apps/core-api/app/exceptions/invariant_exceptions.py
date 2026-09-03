"""RuleInvariant domain exception classes."""

from app.exceptions.base import BaseAppException


class InvariantNotFoundError(BaseAppException):
    """Raised when a rule invariant is not found or not owned by the scenario."""

    def __init__(self, message: str = "Rule invariant not found"):
        super().__init__(message=message, status_code=404)


class InvariantValidationError(BaseAppException):
    """Raised when an invariant's expression references an unknown field."""

    def __init__(self, message: str = "Invalid rule invariant configuration"):
        super().__init__(message=message, status_code=422)
