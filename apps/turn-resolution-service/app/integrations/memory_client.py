"""Memory layer client for Turn Resolution Service.

Real HTTP client for the memory layer (apps/memory-layer, "mem1"). The only
file `context_retrieval.py`/`memory_writer.py` are permitted to call
(CLAUDE.md). The base URL and API key are read only from `app.config`. Never
logs request/response payloads on failure — only the error type — since a
query request carries the player's action text and retrieved facts.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
import structlog

from app.config import settings
from app.exceptions.turn_exceptions import (
    MemoryBatchNotFoundError,
    MemoryLayerUnavailableError,
)
from app.models.memory import (
    BatchStatus,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryQueryRequest,
    MemoryQueryResponse,
)

logger = structlog.get_logger()

EVENT_MEMORY_QUERY_ERROR = "memory_query_error"
EVENT_MEMORY_INGEST_ERROR = "memory_ingest_error"
EVENT_MEMORY_BATCH_STATUS_ERROR = "memory_batch_status_error"
EVENT_MEMORY_BATCH_RETRY_ERROR = "memory_batch_retry_error"

_NOT_FOUND_STATUS_CODE = 404

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Build the memory-layer HTTP client lazily and cache it.

    Lazy construction avoids binding to settings.memory_service_url at
    import time, keeping this module import-safe in any environment
    (tests, CI) regardless of what's configured.
    """
    global _client
    if _client is None:
        headers = {}
        if settings.memory_service_api_key:
            headers["Authorization"] = f"Bearer {settings.memory_service_api_key}"
        _client = httpx.AsyncClient(
            base_url=settings.memory_service_url, headers=headers
        )
    return _client


async def _request(
    method: str,
    path: str,
    timeout_seconds: int,
    event: str,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform one memory-layer HTTP call, translating failures into domain exceptions."""
    try:
        response = await _get_client().request(
            method, path, json=json_body, timeout=timeout_seconds
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.warning(event, error_type="TimeoutError")
        raise MemoryLayerUnavailableError() from exc
    except httpx.ConnectError as exc:
        logger.warning(event, error_type="ConnectError")
        raise MemoryLayerUnavailableError() from exc
    except httpx.HTTPStatusError as exc:
        raise _map_status_error(exc, event) from exc
    return response.json()


def _map_status_error(exc: httpx.HTTPStatusError, event: str) -> Exception:
    status_code = exc.response.status_code
    if status_code == _NOT_FOUND_STATUS_CODE:
        logger.warning(event, error_type="NotFound")
        return MemoryBatchNotFoundError()
    error_type = "ServerError" if status_code >= 500 else "ClientError"
    logger.warning(event, error_type=error_type, status_code=status_code)
    return MemoryLayerUnavailableError()


async def query_memory(request: MemoryQueryRequest) -> MemoryQueryResponse:
    """Query the memory layer for facts relevant to the current turn."""
    data = await _request(
        "POST",
        "/v1/memory/query",
        settings.memory_query_timeout_seconds,
        EVENT_MEMORY_QUERY_ERROR,
        request.model_dump(mode="json"),
    )
    return MemoryQueryResponse.model_validate(data)


async def ingest_batch(request: MemoryIngestRequest) -> MemoryIngestResponse:
    """Submit a batch of recent turns for asynchronous extraction."""
    data = await _request(
        "POST",
        "/v1/memory/ingest",
        settings.memory_ingest_timeout_seconds,
        EVENT_MEMORY_INGEST_ERROR,
        request.model_dump(mode="json"),
    )
    return MemoryIngestResponse.model_validate(data)


async def get_batch_status(batch_id: UUID) -> BatchStatus:
    """Poll the status of a previously submitted ingest batch."""
    data = await _request(
        "GET",
        f"/v1/memory/batch/{batch_id}/status",
        settings.memory_query_timeout_seconds,
        EVENT_MEMORY_BATCH_STATUS_ERROR,
    )
    return BatchStatus.model_validate(data)


async def retry_batch(batch_id: UUID) -> MemoryIngestResponse:
    """Re-trigger a failed or partial ingest batch."""
    data = await _request(
        "POST",
        f"/v1/memory/batch/{batch_id}/retry",
        settings.memory_query_timeout_seconds,
        EVENT_MEMORY_BATCH_RETRY_ERROR,
    )
    return MemoryIngestResponse.model_validate(data)
