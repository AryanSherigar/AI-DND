import pytest
from unittest.mock import patch
from app.services.auth_service import AuthService
from app.repositories.user_repo import UserRepo
from app.exceptions.auth_exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

@pytest.mark.asyncio
async def test_jwt_generation(db_session: AsyncSession):
    auth_service = AuthService(UserRepo(db_session))
    user = await auth_service._upsert_user("test-123", "Test User")
    
    access_token = auth_service.generate_access_token(user)
    refresh_token = auth_service.generate_refresh_token(user)
    
    assert access_token is not None
    assert refresh_token is not None
    
    import jwt
    from app.config import settings
    
    payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == str(user.user_id)
    assert payload["type"] == "access"
    assert payload["token_version"] == 1

@pytest.mark.asyncio
@patch("app.services.auth_service.firebase_auth.verify_id_token")
async def test_verify_firebase_token_success(mock_verify, db_session: AsyncSession):
    mock_verify.return_value = {"uid": "firebase-uid-1", "name": "Firebase User"}
    
    auth_service = AuthService(UserRepo(db_session))
    user = await auth_service.verify_firebase_token_and_upsert_user("valid_token")
    
    assert user.auth_provider_id == "firebase-uid-1"
    assert user.display_name == "Firebase User"

@pytest.mark.asyncio
@patch("app.services.auth_service.firebase_auth.verify_id_token")
async def test_verify_firebase_token_failure(mock_verify, db_session: AsyncSession):
    mock_verify.side_effect = Exception("Expired token")
    
    auth_service = AuthService(UserRepo(db_session))
    with pytest.raises(InvalidTokenError) as exc_info:
        await auth_service.verify_firebase_token_and_upsert_user("invalid_token")
        
    assert "Firebase token verification failed" in str(exc_info.value)
