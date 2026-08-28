from unittest.mock import patch

import pytest
from app.db.models.user import User
from app.main import app as fastapi_app
from app.middleware.auth import get_current_user
from fastapi import APIRouter, Depends
from httpx import AsyncClient

dummy_router = APIRouter()


@dummy_router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"user_id": str(user.user_id), "status": "success"}


fastapi_app.include_router(dummy_router)


@pytest.mark.asyncio
@patch("app.services.auth_service.firebase_auth.verify_id_token")
async def test_exchange_token_success(mock_verify, async_client: AsyncClient):
    mock_verify.return_value = {"uid": "google-uid-1", "name": "Google User"}

    response = await async_client.post(
        "/v1/auth/token", json={"firebase_id_token": "valid-google-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["display_name"] == "Google User"

    # Check that refresh token cookie was set
    cookies = response.cookies
    assert "refresh_token" in cookies


@pytest.mark.asyncio
@patch("app.services.auth_service.firebase_auth.verify_id_token")
async def test_exchange_token_invalid(mock_verify, async_client: AsyncClient):
    mock_verify.side_effect = Exception("Invalid Firebase token")

    response = await async_client.post(
        "/v1/auth/token", json={"firebase_id_token": "invalid-token"}
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Firebase token verification failed: Invalid Firebase token"
    )


@pytest.mark.asyncio
@patch("app.services.auth_service.firebase_auth.verify_id_token")
async def test_refresh_token_flow(mock_verify, async_client: AsyncClient):
    mock_verify.return_value = {"uid": "google-uid-refresh", "name": "Refresh User"}

    # 1. Get initial tokens
    response1 = await async_client.post(
        "/v1/auth/token", json={"firebase_id_token": "valid-token"}
    )
    assert response1.status_code == 200
    refresh_token = response1.cookies.get("refresh_token")
    assert refresh_token is not None

    # 2. Use refresh token to get new access token
    response2 = await async_client.post(
        "/v1/auth/refresh", cookies={"refresh_token": refresh_token}
    )
    assert response2.status_code == 200
    data = response2.json()
    assert "access_token" in data
    assert data["user"]["display_name"] == "Refresh User"

    # 3. Check that a NEW refresh token cookie was set
    new_refresh_token = response2.cookies.get("refresh_token")
    assert new_refresh_token is not None
    # Token value might be identical if generated in the same second, so just verify it exists


@pytest.mark.asyncio
async def test_refresh_token_missing(async_client: AsyncClient):
    response = await async_client.post("/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token missing"


@pytest.mark.asyncio
async def test_refresh_token_invalid(async_client: AsyncClient):
    response = await async_client.post(
        "/v1/auth/refresh", cookies={"refresh_token": "invalid-jwt-token"}
    )
    assert response.status_code == 401
    assert "Invalid or expired refresh token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_protected_route_without_auth(async_client: AsyncClient):
    response = await async_client.get("/protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(async_client: AsyncClient):
    response = await async_client.get(
        "/protected", headers={"Authorization": "Bearer invalid_token_value"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token"


@pytest.mark.asyncio
@patch("app.services.auth_service.firebase_auth.verify_id_token")
async def test_protected_route_with_valid_token(mock_verify, async_client: AsyncClient):
    mock_verify.return_value = {"uid": "google-uid-protected", "name": "Protected User"}

    # Get token
    auth_resp = await async_client.post(
        "/v1/auth/token", json={"firebase_id_token": "valid-token"}
    )
    access_token = auth_resp.json()["access_token"]

    # Access protected route
    response = await async_client.get(
        "/protected", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
