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


class ParticipantAccessDeniedError(BaseAppException):
    """Raised when the acting participant does not belong to the authenticated user."""

    def __init__(
        self, message: str = "Participant does not belong to authenticated user"
    ):
        super().__init__(message=message, status_code=403)


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


class MinigameResultRequiredError(BaseAppException):
    """Raised when a normal action is submitted while a minigame is pending
    resolution — a playthrough can never silently drop a pending minigame."""

    def __init__(
        self,
        message: str = "A minigame result must be submitted before any other action",
    ):
        super().__init__(message=message, status_code=409)


class MinigameResultMismatchError(BaseAppException):
    """Raised when a submitted minigame result doesn't match the pending
    minigame, or when none is pending at all."""

    def __init__(
        self,
        message: str = "Submitted minigame result does not match the pending minigame",
    ):
        super().__init__(message=message, status_code=409)


class MemoryLayerUnavailableError(BaseAppException):
    """Raised when the memory layer is transiently unavailable (timeout, 5xx,
    connection error, or an unexpected client error)."""

    def __init__(self, message: str = "Memory layer is temporarily unavailable"):
        super().__init__(message=message, status_code=502)


class MemoryBatchNotFoundError(BaseAppException):
    """Raised when a batch_id is unknown to the memory layer."""

    def __init__(self, message: str = "Memory batch not found"):
        super().__init__(message=message, status_code=404)


class OptimisticLockError(BaseAppException):
    """Raised when a concurrent write updated the playthrough state first."""

    def __init__(
        self, message: str = "Playthrough state was modified by another transaction"
    ):
        super().__init__(message=message, status_code=409)
