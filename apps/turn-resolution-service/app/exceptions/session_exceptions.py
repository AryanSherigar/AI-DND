"""Session/spectate domain exception classes."""

from app.exceptions.base import BaseAppException


class InvalidShareTokenError(BaseAppException):
    """Raised when a spectate share token is missing, unknown, or the wrong mode."""

    def __init__(self, message: str = "Invalid or expired share token"):
        super().__init__(message=message, status_code=403)
