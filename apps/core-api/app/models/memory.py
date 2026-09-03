"""Canonical memory layer models for Core API.

Defines Pydantic v2 schemas for POST /v1/memory/query, POST /v1/memory/ingest,
authoring-time template ingestion, and playthrough space cloning.
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


class EntityIngestPayload(BaseModel):
    """Direct-write shape for one entity at authoring-time ingestion."""

    entity_id: UUID
    entity_type: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None


class FactIngestPayload(BaseModel):
    """Direct-write shape for one fact at authoring-time ingestion."""

    fact_id: UUID
    subject_entity_id: UUID
    predicate: str
    object_entity_id: UUID | None = None
    object_literal: str | None = None
    valid_from: str | None = None
    when_active: dict[str, Any] | None = None
    hidden: bool = False


class MemoryTemplateIngestRequest(BaseModel):
    """Request body for authoring-time template ingestion.

    world_data is populated for newbie mode (LLM extraction); entities/facts
    are populated for master mode (direct write, no LLM extraction) — a
    scenario populates exactly one pair, never both, matching its fixed mode.
    """

    scenario_id: UUID
    mode: Literal["newbie", "master"]
    world_data: dict[str, Any] = Field(default_factory=dict)
    entities: list[EntityIngestPayload] = Field(default_factory=list)
    facts: list[FactIngestPayload] = Field(default_factory=list)


class MemoryTemplateIngestResponse(BaseModel):
    """Response body for authoring-time template ingestion."""

    template_space_id: UUID


class MemoryTemplateCloneRequest(BaseModel):
    """Request body for cloning scenario template memory space to playthrough."""

    scenario_id: UUID
    playthrough_id: UUID


class MemoryTemplateCloneResponse(BaseModel):
    """Response body for memory space cloning."""

    playthrough_space_id: UUID
