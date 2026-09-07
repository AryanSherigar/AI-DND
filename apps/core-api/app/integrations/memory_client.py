"""Memory layer client for Core API.

Real HTTP client for mem1 (apps/memory-layer). The only file permitted to
call the memory layer (CLAUDE.md). The base URL and API key are read only
from `app.config`.

Authoring-time ingestion accepts two mutually exclusive request shapes,
never both on the same request: newbie mode's world_data (LLM extraction)
and master mode's entities/facts (direct write, no LLM extraction — the
creator authored every entity and fact precisely, so nothing reinterprets
them). mem1's own wire contract for POST /v1/memory/template/ingest has no
top-level entities/facts field — master-mode entities/facts are folded into
world_data, keyed by canonical_name rather than this product's entity UUIDs
(see _build_template_ingest_body).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
import structlog

from app.config import settings
from app.exceptions.memory_exceptions import (
    MemoryBatchNotFoundError,
    MemoryLayerUnavailableError,
)
from app.models.memory import (
    BatchStatus,
    EntityIngestPayload,
    FactIngestPayload,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryQueryRequest,
    MemoryQueryResponse,
    MemoryTemplateCloneRequest,
    MemoryTemplateCloneResponse,
    MemoryTemplateIngestRequest,
    MemoryTemplateIngestResponse,
)

logger = structlog.get_logger()

EVENT_MEMORY_QUERY_ERROR = "memory_query_error"
EVENT_MEMORY_INGEST_ERROR = "memory_ingest_error"
EVENT_MEMORY_BATCH_STATUS_ERROR = "memory_batch_status_error"
EVENT_MEMORY_BATCH_RETRY_ERROR = "memory_batch_retry_error"
EVENT_MEMORY_TEMPLATE_INGEST_ERROR = "memory_template_ingest_error"
EVENT_MEMORY_CLONE_ERROR = "memory_clone_error"

_client: httpx.AsyncClient | None = None

_NOT_FOUND_STATUS_CODE = 404
_SERVER_ERROR_STATUS_CODE = 500


def _get_client() -> httpx.AsyncClient:
    """Build the memory-layer HTTP client lazily and cache it.

    Lazy construction avoids reading settings.memory_service_url at import
    time, matching gemini_client._get_client()'s rationale.
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
    """Perform one memory-layer HTTP call, translating transport failures into
    domain exceptions. Never logs the request/response payload itself."""
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


def _map_status_error(
    exc: httpx.HTTPStatusError, event: str
) -> MemoryLayerUnavailableError | MemoryBatchNotFoundError:
    status = exc.response.status_code
    if status == _NOT_FOUND_STATUS_CODE:
        logger.warning(event, error_type="NotFound")
        return MemoryBatchNotFoundError()
    error_type = "ServerError" if status >= _SERVER_ERROR_STATUS_CODE else "ClientError"
    logger.warning(event, error_type=error_type, status_code=status)
    return MemoryLayerUnavailableError()


async def query_memory(request: MemoryQueryRequest) -> MemoryQueryResponse:
    """Structured retrieval for authoring/tool flows."""
    data = await _request(
        "POST",
        "/v1/memory/query",
        settings.memory_query_timeout_seconds,
        EVENT_MEMORY_QUERY_ERROR,
        request.model_dump(mode="json"),
    )
    return MemoryQueryResponse.model_validate(data)


async def ingest_batch(request: MemoryIngestRequest) -> MemoryIngestResponse:
    """Batched extraction submission."""
    data = await _request(
        "POST",
        "/v1/memory/ingest",
        settings.memory_ingest_timeout_seconds,
        EVENT_MEMORY_INGEST_ERROR,
        request.model_dump(mode="json"),
    )
    return MemoryIngestResponse.model_validate(data)


async def get_batch_status(batch_id: UUID) -> BatchStatus:
    """Poll an ingest batch's status."""
    data = await _request(
        "GET",
        f"/v1/memory/batch/{batch_id}/status",
        settings.memory_query_timeout_seconds,
        EVENT_MEMORY_BATCH_STATUS_ERROR,
    )
    return BatchStatus.model_validate(data)


async def retry_batch(batch_id: UUID) -> MemoryIngestResponse:
    """Re-trigger a failed/partial ingest batch."""
    data = await _request(
        "POST",
        f"/v1/memory/batch/{batch_id}/retry",
        settings.memory_query_timeout_seconds,
        EVENT_MEMORY_BATCH_RETRY_ERROR,
    )
    return MemoryIngestResponse.model_validate(data)


async def ingest_scenario_template(
    request: MemoryTemplateIngestRequest,
) -> MemoryTemplateIngestResponse:
    """Authoring-time ingestion at scenario publish (ADR-7)."""
    body = _build_template_ingest_body(request)
    data = await _request(
        "POST",
        "/v1/memory/template/ingest",
        settings.memory_template_timeout_seconds,
        EVENT_MEMORY_TEMPLATE_INGEST_ERROR,
        body,
    )
    return MemoryTemplateIngestResponse.model_validate(data)


async def clone_template_memory_space(
    request: MemoryTemplateCloneRequest,
) -> MemoryTemplateCloneResponse:
    """Clone a scenario's template memory space into a new playthrough space."""
    path = f"/v1/memory/playthrough/{request.playthrough_id}/init"
    data = await _request(
        "POST",
        path,
        settings.memory_clone_timeout_seconds,
        EVENT_MEMORY_CLONE_ERROR,
        request.model_dump(mode="json"),
    )
    return MemoryTemplateCloneResponse.model_validate(data)


def _build_template_ingest_body(
    request: MemoryTemplateIngestRequest,
) -> dict[str, Any]:
    """Translate the domain request into mem1's real wire shape.

    mem1's POST /v1/memory/template/ingest has only scenario_id/mode/
    world_data on the wire -- master-mode entities/facts are folded into
    world_data, keyed by canonical_name (mem1 has no notion of this
    product's entity UUIDs).

    Newbie mode: mem1 requires world_data.lore_text, but Studio's authoring
    payload stores that prose under worldLore. Map it here rather than in
    mem1 or Studio, since this file is the only permitted mem1 wire boundary.
    """
    if request.mode == "newbie":
        world_data = {
            **request.world_data,
            "lore_text": request.world_data.get("worldLore"),
        }
    else:
        canonical_names = {e.entity_id: e.canonical_name for e in request.entities}
        world_data = {
            "entities": [_entity_to_wire(e) for e in request.entities],
            "facts": [_fact_to_wire(f, canonical_names) for f in request.facts],
        }
    return {
        "scenario_id": str(request.scenario_id),
        "mode": request.mode,
        "world_data": world_data,
    }


def _entity_to_wire(entity: EntityIngestPayload) -> dict[str, Any]:
    return {
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "aliases": entity.aliases,
        "description": entity.description,
    }


def _fact_to_wire(
    fact: FactIngestPayload, canonical_names: dict[UUID, str]
) -> dict[str, Any]:
    object_canonical_name = (
        canonical_names.get(fact.object_entity_id) if fact.object_entity_id else None
    )
    return {
        "subject_canonical_name": canonical_names[fact.subject_entity_id],
        "predicate": fact.predicate,
        "object_canonical_name": object_canonical_name,
        "object_literal": fact.object_literal,
        "valid_from": fact.valid_from,
        "when_active": fact.when_active,
        "hidden": fact.hidden,
        "external_fact_id": str(fact.fact_id),
        "superseded_fact_id": (
            str(fact.superseded_fact_id) if fact.superseded_fact_id else None
        ),
    }
