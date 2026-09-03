import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.exceptions.auth_exceptions import InvalidTokenError
from app.models.auth import CurrentUser

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> CurrentUser:
    if settings.environment in ("development", "testing"):
        dev_user_id = request.headers.get("x-dev-user-id")
        if dev_user_id:
            try:
                # We trust the dev header completely in TRS dev bypass
                return CurrentUser(user_id=uuid.UUID(dev_user_id), token_version=1)
            except ValueError:
                raise InvalidTokenError("Invalid UUID format in dev header")

    if not credentials:
        raise InvalidTokenError("Not authenticated")

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")

        user_id = payload.get("sub")
        token_version = payload.get("token_version")

        return CurrentUser(user_id=uuid.UUID(user_id), token_version=token_version)
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid or expired access token")
