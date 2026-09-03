import uuid
from typing import Annotated

import jwt
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.connection import get_db_session
from app.db.models.user import User
from app.exceptions.auth_exceptions import InvalidTokenError
from app.repositories.user_repo import UserRepo

security = HTTPBearer(auto_error=False)
optional_security = HTTPBearer(auto_error=False)


def _bind_user_context(user: User) -> None:
    structlog.contextvars.bind_contextvars(user_id=str(user.user_id))


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    if settings.environment in ("development", "testing"):
        dev_user_id = request.headers.get("x-dev-user-id")
        if dev_user_id:
            user_repo = UserRepo(session)
            try:
                user_uuid = uuid.UUID(dev_user_id)
                user = await user_repo.get_by_id(user_uuid)
                if not user:
                    user = User(
                        user_id=user_uuid,
                        auth_provider_id=f"dev_{dev_user_id}",
                        display_name="Dev User",
                    )
                    session.add(user)
                    await session.commit()
                _bind_user_context(user)
                return user
            except ValueError:
                pass
            raise InvalidTokenError("Dev user not found or invalid UUID format")

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

        user_repo = UserRepo(session)
        user = await user_repo.get_by_id(uuid.UUID(user_id))

        if not user or user.token_version != token_version:
            raise InvalidTokenError("Token revoked or user not found")

        _bind_user_context(user)
        return user
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid or expired access token")


async def get_optional_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(optional_security)
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User | None:
    if settings.environment in ("development", "testing"):
        dev_user_id = request.headers.get("x-dev-user-id")
        if dev_user_id:
            user_repo = UserRepo(session)
            try:
                user_uuid = uuid.UUID(dev_user_id)
                user = await user_repo.get_by_id(user_uuid)
                if not user:
                    user = User(
                        user_id=user_uuid,
                        auth_provider_id=f"dev_{dev_user_id}",
                        display_name="Dev User",
                    )
                    session.add(user)
                    await session.commit()
                _bind_user_context(user)
                return user
            except ValueError:
                pass

    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        token_version = payload.get("token_version")

        user_repo = UserRepo(session)
        user = await user_repo.get_by_id(uuid.UUID(user_id))

        if not user or user.token_version != token_version:
            return None

        _bind_user_context(user)
        return user
    except jwt.InvalidTokenError:
        return None
