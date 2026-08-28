from app.config import settings
from app.db.connection import get_db_session
from app.exceptions.auth_exceptions import InvalidTokenError
from app.models.auth import TokenExchangeRequest, TokenResponse, UserResponse
from app.repositories.user_repo import UserRepo
from app.services.auth_service import AuthService
from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def get_auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(UserRepo(session))


@router.post("/token", response_model=TokenResponse)
async def exchange_token(
    req: TokenExchangeRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    user = await auth_service.verify_firebase_token_and_upsert_user(
        req.firebase_id_token
    )

    access_token = auth_service.generate_access_token(user)
    refresh_token = auth_service.generate_refresh_token(user)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        path="/v1/auth/refresh",
        max_age=settings.jwt_refresh_expire_days * 24 * 60 * 60,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    session: AsyncSession = Depends(get_db_session),
):
    if not refresh_token:
        raise InvalidTokenError("Refresh token missing")

    import jwt

    try:
        payload = jwt.decode(
            refresh_token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Invalid token type")

        user_id = payload.get("sub")
        token_version = payload.get("token_version")

        user_repo = UserRepo(session)
        import uuid

        user = await user_repo.get_by_id(uuid.UUID(user_id))

        if not user or user.token_version != token_version:
            raise InvalidTokenError("Token revoked or user not found")

        access_token = auth_service.generate_access_token(user)
        new_refresh_token = auth_service.generate_refresh_token(user)

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=settings.environment != "development",
            samesite="lax",
            path="/v1/auth/refresh",
            max_age=settings.jwt_refresh_expire_days * 24 * 60 * 60,
        )

        return TokenResponse(
            access_token=access_token,
            expires_in=settings.jwt_access_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid or expired refresh token")
