from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.routes import _ping_postgres_pool
from api.server import app

client = TestClient(app)


def test_health() -> None:
    """Liveness probe test (/health) expecting immediate status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_health_offline() -> None:
    """Readiness probe test (/v1/health) when databases are offline."""
    start_time = time.perf_counter()
    response = client.get("/v1/health")
    duration = time.perf_counter() - start_time

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert "down" in data["postgres"]
    assert "down" in data["hydradb"]
    assert duration < 2.0


def test_readiness_health_all_up() -> None:
    """Readiness probe test when both Postgres and HydraDB are healthy."""
    with (
        patch("api.routes._check_postgres", return_value="up"),
        patch("api.routes._check_hydradb", return_value="up"),
    ):
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "postgres": "up",
            "hydradb": "up",
        }


def test_readiness_health_postgres_down() -> None:
    """Readiness probe test when Postgres is down and HydraDB is healthy."""
    with (
        patch("api.routes._check_postgres", return_value="down (TimeoutError)"),
        patch("api.routes._check_hydradb", return_value="up"),
    ):
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "degraded",
            "postgres": "down (TimeoutError)",
            "hydradb": "up",
        }


def test_readiness_health_hydradb_unhealthy() -> None:
    """Readiness probe test when HydraDB returns a 5xx error."""
    with (
        patch("api.routes._check_postgres", return_value="up"),
        patch("api.routes._check_hydradb", return_value="unhealthy (503)"),
    ):
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "degraded",
            "postgres": "up",
            "hydradb": "unhealthy (503)",
        }


def test_ping_postgres_pool() -> None:
    """Test that _ping_postgres_pool acquires a connection and runs SELECT 1."""
    mock_cursor = MagicMock()
    mock_connection = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_connection

    _ping_postgres_pool(mock_pool)
    mock_cursor.execute.assert_called_once_with("SELECT 1")
