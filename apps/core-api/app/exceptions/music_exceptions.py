"""Scenario music domain exception classes."""

from app.exceptions.base import BaseAppException


class MusicValidationError(BaseAppException):
    """Raised when an uploaded track or generation request fails validation."""

    def __init__(self, message: str = "Invalid music track"):
        super().__init__(message=message, status_code=400)


class MusicGenerationError(BaseAppException):
    """Raised when AI music generation fails."""

    def __init__(self, message: str = "Music generation is temporarily unavailable"):
        super().__init__(message=message, status_code=502)


class MusicJobNotFoundError(BaseAppException):
    """Raised when a referenced generation job doesn't exist or isn't owned by the caller."""

    def __init__(self, message: str = "Generation job not found"):
        super().__init__(message=message, status_code=404)


class MusicGenerationQuotaExceededError(BaseAppException):
    """Raised when a scenario or creator has hit its generation quota."""

    def __init__(self, message: str = "Music generation quota exceeded"):
        super().__init__(message=message, status_code=429)
