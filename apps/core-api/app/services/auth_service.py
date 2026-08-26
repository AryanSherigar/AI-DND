from datetime import datetime, timedelta, timezone
import jwt
from firebase_admin import auth as firebase_auth
from app.config import settings
from app.repositories.user_repo import UserRepo
from app.db.models.user import User
from app.exceptions.auth_exceptions import InvalidTokenError
import structlog

logger = structlog.get_logger()

class AuthService:
    def __init__(self, user_repo: UserRepo):
        self.user_repo = user_repo

    async def verify_firebase_token_and_upsert_user(self, firebase_token: str) -> User:
        if settings.environment == "development" and not settings.firebase_project_id:
            # Bypass/mock for local testing without Firebase
            logger.info("Using dev bypass for firebase auth")
            return await self._upsert_user("dev-firebase-id-123", "Dev User")

        try:
            # Firebase admin calls are synchronous, but they hit an API.
            decoded_token = firebase_auth.verify_id_token(firebase_token, check_revoked=True)
            uid = decoded_token.get("uid")
            name = decoded_token.get("name", "Unknown User")
            return await self._upsert_user(uid, name)
        except Exception as e:
            logger.error("firebase_verification_failed", error=str(e))
            raise InvalidTokenError(f"Firebase token verification failed: {str(e)}")

    async def _upsert_user(self, auth_provider_id: str, display_name: str) -> User:
        user = await self.user_repo.get_by_auth_provider_id(auth_provider_id)
        if not user:
            user = await self.user_repo.create(auth_provider_id, display_name)
        return user

    def generate_access_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_expire_minutes)
        to_encode = {
            "sub": str(user.user_id),
            "exp": expire,
            "token_version": user.token_version,
            "type": "access"
        }
        return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)

    def generate_refresh_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
        to_encode = {
            "sub": str(user.user_id),
            "exp": expire,
            "token_version": user.token_version,
            "type": "refresh"
        }
        return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
