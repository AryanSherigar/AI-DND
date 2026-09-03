from datetime import datetime, timedelta, timezone

import jwt
import structlog
from firebase_admin import auth as firebase_auth

from app.config import settings
from app.db.models.user import User
from app.exceptions.auth_exceptions import InvalidTokenError
from app.repositories.user_repo import UserRepo

logger = structlog.get_logger()

EVENT_AUTH_DEV_BYPASS_USED = "auth_dev_bypass_used"
EVENT_AUTH_TOKEN_VERIFICATION_FAILED = "auth_token_verification_failed"


class AuthService:
    def __init__(self, user_repo: UserRepo):
        self.user_repo = user_repo

    async def verify_firebase_token_and_upsert_user(self, firebase_token: str) -> User:
        if firebase_token == "mock-dev-token" or (
            settings.environment in ("development", "testing")
            and not settings.firebase_project_id
        ):
            # Bypass/mock for local testing without Firebase
            logger.info(EVENT_AUTH_DEV_BYPASS_USED)
            return await self._upsert_user("dev-firebase-id-123", "Dev User")

        try:
            if settings.firebase_credentials_path or settings.environment == "testing":
                decoded_token = firebase_auth.verify_id_token(firebase_token)
            else:
                from google.auth.transport import requests as google_requests
                from google.oauth2 import id_token as google_id_token

                req = google_requests.Request()
                decoded_token = google_id_token.verify_firebase_token(
                    firebase_token, req, audience=settings.firebase_project_id
                )

            uid = decoded_token.get("uid") or decoded_token.get("sub") or ""
            email = decoded_token.get("email", "")
            name = decoded_token.get("name") or (
                email.split("@")[0] if email else "User"
            )
            return await self._upsert_user(uid, name)
        except Exception as e:
            logger.warning(EVENT_AUTH_TOKEN_VERIFICATION_FAILED, error=str(e))
            raise InvalidTokenError(f"Firebase token verification failed: {e!s}")

    async def _upsert_user(self, auth_provider_id: str, display_name: str) -> User:
        user = await self.user_repo.get_by_auth_provider_id(auth_provider_id)
        if not user:
            user = await self.user_repo.create(auth_provider_id, display_name)
        return user

    def generate_access_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_expire_minutes
        )
        to_encode = {
            "sub": str(user.user_id),
            "exp": expire,
            "token_version": user.token_version,
            "type": "access",
        }
        return jwt.encode(
            to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
        )

    def generate_refresh_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_expire_days
        )
        to_encode = {
            "sub": str(user.user_id),
            "exp": expire,
            "token_version": user.token_version,
            "type": "refresh",
        }
        return jwt.encode(
            to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
        )
