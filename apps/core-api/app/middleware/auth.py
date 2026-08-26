import jwt
from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.connection import get_db_session
from app.config import settings
from app.repositories.user_repo import UserRepo
from app.exceptions.auth_exceptions import InvalidTokenError
from app.db.models.user import User
import uuid

security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> User:
    if settings.environment == "development":
        dev_user_id = request.headers.get("x-dev-user-id")
        if dev_user_id:
            user_repo = UserRepo(session)
            try:
                user = await user_repo.get_by_id(uuid.UUID(dev_user_id))
                if user:
                    return user
            except ValueError:
                pass
            raise InvalidTokenError("Dev user not found or invalid UUID format")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")
            
        user_id = payload.get("sub")
        token_version = payload.get("token_version")
        
        user_repo = UserRepo(session)
        user = await user_repo.get_by_id(uuid.UUID(user_id))
        
        if not user or user.token_version != token_version:
            raise InvalidTokenError("Token revoked or user not found")
            
        return user
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid or expired access token")
