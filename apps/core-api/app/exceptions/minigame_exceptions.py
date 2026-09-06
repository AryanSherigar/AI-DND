"""Minigame domain exception classes."""

from app.exceptions.base import BaseAppException


class MinigameModeError(BaseAppException):
    """Raised when a Minigames operation is attempted on a non-master-mode
    scenario."""

    def __init__(
        self, message: str = "Minigames are only available for master-mode scenarios"
    ):
        super().__init__(message=message, status_code=422)


class MinigameNotFoundError(BaseAppException):
    """Raised when a minigame is not found or does not belong to the scenario."""

    def __init__(self, message: str = "Minigame not found"):
        super().__init__(message=message, status_code=404)


class MinigameValidationError(BaseAppException):
    """Raised when a minigame's type/config or outcome/mutation pairing is
    invalid, or its trigger_condition_expression references an unknown
    field."""

    def __init__(self, message: str = "Invalid minigame configuration"):
        super().__init__(message=message, status_code=422)


class MinigameUnreachableError(BaseAppException):
    """Raised when a replit_embed minigame's URL fails the save-time
    reachability check after retrying."""

    def __init__(self, url: str = ""):
        message = (
            f"Could not reach the Replit-hosted minigame at {url!r} after retrying"
            if url
            else "Could not reach the Replit-hosted minigame URL after retrying"
        )
        super().__init__(message=message, status_code=422)
