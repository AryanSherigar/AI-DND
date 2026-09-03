"""Canonical memory layer models for Turn Resolution Service.

Defines Pydantic v2 schemas for POST /v1/memory/query, POST /v1/memory/ingest,
and GET /v1/memory/batch/{batch_id}/status endpoints.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryQueryRequest(BaseModel):
    """Request body for POST /v1/memory/query."""

    scenario_id: UUID
    playthrough_id: UUID
    participant_id: UUID
    query_text: str
    checkpoint: str
    game_state: dict[str, Any] = Field(default_factory=dict)
    as_of_turn: int | None = None


class Fact(BaseModel):
    """A single structured fact returned by retrieval."""

    fact_id: UUID
    subject: str
    predicate: str
    object: str
    valid_from: str | None = None
    valid_until: str | None = None
    confidence: float
    hidden: bool = False


class MemoryQueryResponse(BaseModel):
    """Response body for POST /v1/memory/query."""

    facts: list[Fact]
    abstained: bool
    resolved_time_point: str | None = None


class TurnBatchEntry(BaseModel):
    """A single turn's text within an ingest batch."""

    turn_number: int
    text: str
    participant_id: UUID


class MemoryIngestRequest(BaseModel):
    """Request body for POST /v1/memory/ingest."""

    scenario_id: UUID
    playthrough_id: UUID
    turns_batch: list[TurnBatchEntry]
    recent_context_turns: list[TurnBatchEntry] = Field(default_factory=list)


class MemoryIngestResponse(BaseModel):
    """Response body for POST /v1/memory/ingest (202 Accepted)."""

    batch_id: UUID


class BatchStatus(BaseModel):
    """Response body for GET /v1/memory/batch/{batch_id}/status."""

    batch_id: UUID
    status: Literal["pending", "succeeded", "failed", "partial"]
    facts_created: int
    error: str | None = None
    retryable: bool = False
