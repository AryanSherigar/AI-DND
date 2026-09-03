"""Fact domain exception classes."""

from app.exceptions.base import BaseAppException


class FactNotFoundError(BaseAppException):
    """Raised when a fact is not found or does not belong to the scenario."""

    def __init__(self, message: str = "Fact not found"):
        super().__init__(message=message, status_code=404)


class FactInvalidReferenceError(BaseAppException):
    """Raised when a fact's subject/object entity reference is invalid."""

    def __init__(self, message: str = "Invalid entity reference"):
        super().__init__(message=message, status_code=422)


class FactValidationError(BaseAppException):
    """Raised when a fact's shape fails domain validation (e.g. object
    exclusivity, circular supersession)."""

    def __init__(self, message: str = "Invalid fact configuration"):
        super().__init__(message=message, status_code=422)
