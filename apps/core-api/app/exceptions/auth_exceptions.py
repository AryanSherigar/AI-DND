from app.exceptions.base import BaseAppException


class AuthError(BaseAppException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class InvalidTokenError(AuthError):
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message)
