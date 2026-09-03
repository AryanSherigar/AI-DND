"""Playthrough domain exception classes."""

from app.exceptions.base import BaseAppException


class PlaythroughNotFoundError(BaseAppException):
    """Raised when a playthrough is not found."""

    def __init__(self, message: str = "Playthrough not found"):
        super().__init__(message=message, status_code=404)


class PlaythroughAccessDeniedError(BaseAppException):
    """Raised when a user is not a participant of the playthrough."""

    def __init__(self, message: str = "Access denied for this playthrough"):
        super().__init__(message=message, status_code=403)


class ScenarioNotPublishedError(BaseAppException):
    """Raised when a playthrough is attempted on a non-published scenario."""

    def __init__(self, message: str = "Scenario is not published"):
        super().__init__(message=message, status_code=409)


class InvalidSetupValuesError(BaseAppException):
    """Raised when setup_values fail validation against setup_schema."""

    def __init__(self, message: str = "Invalid setup values"):
        super().__init__(message=message, status_code=422)


class PlaythroughMemoryCloneError(BaseAppException):
    """Raised when the memory-layer template clone fails at creation time."""

    def __init__(self, message: str = "Failed to initialize playthrough memory"):
        super().__init__(message=message, status_code=502)


class InvalidShareTokenError(BaseAppException):
    """Raised when a share token is missing, unknown, or the wrong mode."""

    def __init__(self, message: str = "Invalid or expired share token"):
        super().__init__(message=message, status_code=404)


class SoloScenarioJoinError(BaseAppException):
    """Raised when joining a scenario that only supports solo play."""

    def __init__(self, message: str = "This scenario does not support multiplayer"):
        super().__init__(message=message, status_code=409)


class PlaythroughNotJoinableError(BaseAppException):
    """Raised when attempting to join a non-active playthrough."""

    def __init__(self, message: str = "This playthrough can no longer be joined"):
        super().__init__(message=message, status_code=409)
