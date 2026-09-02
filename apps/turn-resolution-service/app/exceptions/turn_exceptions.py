"""Turn pipeline domain exception classes."""

from app.exceptions.base import BaseAppException


class PlaythroughNotActiveError(BaseAppException):
    """Raised when a turn is submitted against a missing or non-active playthrough."""

    def __init__(self, message: str = "Playthrough is not active"):
        super().__init__(message=message, status_code=409)


class ParticipantNotFoundError(BaseAppException):
    """Raised when the acting participant doesn't belong to the playthrough."""

    def __init__(self, message: str = "Participant not found"):
        super().__init__(message=message, status_code=404)


class TurnOrderError(BaseAppException):
    """Raised when a participant acts out of turn in a multiplayer playthrough."""

    def __init__(self, message: str = "It is not this participant's turn"):
        super().__init__(message=message, status_code=409)


class GeminiUnavailableError(BaseAppException):
    """Raised when Gemini is transiently unavailable (timeout, 5xx, rate limit)."""

    def __init__(self, message: str = "Narrator is temporarily unavailable"):
        super().__init__(message=message, status_code=502)


class NarrationGenerationError(BaseAppException):
    """Raised when Gemini narration generation fails after retries."""

    def __init__(self, message: str = "Narration generation failed"):
        super().__init__(message=message, status_code=502)


class StateWriteError(BaseAppException):
    """Raised when persisting turn state fails after retries."""

    def __init__(self, message: str = "Failed to persist turn state"):
        super().__init__(message=message, status_code=500)
