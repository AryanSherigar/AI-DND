"""Wire schemas for the AI-DND memory contract (Milestone 1 of the AI-DND
bridge). Field-for-field matches AI-DND's own mock (`app/models/memory.py` in
both `apps/turn-resolution-service` and `apps/core-api`) so its real client
decodes these responses with zero translation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryQueryRequest(BaseModel):
    """Request body for POST /v1/memory/query.

    `playthrough_id` is mem1's fact-isolation key (`context_id`) under the
    hood -- see the AI-DND bridge plan's identifier mapping. `scenario_id`
    derives the template context used for checkpoint ordering and correlation;
    `participant_id` gates participant-scoped facts during retrieval.
    """

    scenario_id: UUID
    playthrough_id: UUID
    participant_id: UUID
    query_text: str
    checkpoint: str
    game_state: dict[str, Any] = Field(default_factory=dict)
    as_of_turn: int | None = None


class Fact(BaseModel):
    fact_id: str
    subject: str
    predicate: str
    object: str
    valid_from: str | None = None
    valid_until: str | None = None
    confidence: float
    # AI-DND memory-layer contract additions. `hidden`: author-marked
    # secret, returned as-is -- mem1 never filters by it, the caller's own
    # `revealed_facts` override does. `when_active`: returned instead of
    # evaluated server-side (Gap B, accepted) -- `None` means always
    # active; the caller evaluates a present expression with its own
    # grammar (a superset of this service's own `expression_eval.py`).
    hidden: bool = False
    when_active: dict[str, Any] | None = None


class MemoryQueryResponse(BaseModel):
    facts: list[Fact]
    abstained: bool
    resolved_time_point: str | None = None


class TurnBatchEntry(BaseModel):
    """A single turn's text within an ingest batch (Milestone 2)."""

    turn_number: int
    text: str
    participant_id: UUID
    # Optional real event time for this turn -- honored exactly when given;
    # falls back to a deterministic synthetic time derived from turn_number
    # alone when absent (see MemoryEngine.submit_batch). Never required, so
    # existing callers are unaffected.
    occurred_at: datetime | None = None


class MemoryIngestRequest(BaseModel):
    """Request body for POST /v1/memory/ingest (Milestone 2). `playthrough_id`
    maps to mem1's `context_id`, same as `MemoryQueryRequest`.
    `recent_context_turns` is accepted for contract parity (AI-DND's own ADR-5
    catchup-batch shape) but not yet given separate treatment from
    `turns_batch` -- mem1 ingests every entry in both the same way."""

    scenario_id: UUID
    playthrough_id: UUID
    turns_batch: list[TurnBatchEntry]
    recent_context_turns: list[TurnBatchEntry] = Field(default_factory=list)


class MemoryIngestResponse(BaseModel):
    batch_id: str


class BatchStatus(BaseModel):
    batch_id: str
    status: Literal["pending", "succeeded", "failed", "partial"]
    facts_created: int
    error: str | None = None
    retryable: bool = False


class MemoryTemplateIngestRequest(BaseModel):
    """Request body for authoring-time template ingestion (Milestone 3).
    Field-for-field matches AI-DND's real `apps/core-api/app/models/memory.py`
    -- `world_data` is an untyped `dict[str, Any]` there too (the RFC leaves
    `Scenario.world_data` "flexible during implementation"), so mem1 defines
    its own expected internal shape and validates it explicitly rather than
    trusting an implicit one:

      newbie mode: {"lore_text": str}
      master mode: {
        "entities": [{"canonical_name": str, "entity_type": str,
                       "aliases": [str], "description": str | None}, ...],
        "facts": [{"subject_canonical_name": str, "predicate": str,
                    "object_canonical_name": str | None, "object_literal": str | None,
                    "valid_from": str | None (ISO 8601), "when_active": dict | None,
                    "checkpoint": str | None,
                    "visible_to_participant_id": str | None,  # optional; None = visible to every participant
                    "hidden": bool,  # optional, default False -- author-marked secret; mem1 returns it
                        # as-is on every Fact response, never filters by it (client applies its own
                        # revealed_facts override)
                    "external_fact_id": str | None,  # optional -- this fact's own caller-assigned id,
                        # so a LATER fact in this same request (or a later request) can supersede it
                    "superseded_fact_id": str | None},  # optional -- another fact's external_fact_id;
                        # supersession is authoritative over currency/when_active once resolved
                   ...],
        "checkpoints": [str, ...] | None,  # Milestone 5: the scenario's
            # ordered checkpoint list (Scenario.checkpoints, master mode
            # only) -- required once per scenario for a fact's `checkpoint`
            # to mean anything at retrieval time; a fact referencing a
            # checkpoint with no ordering ever stored is a config gap that
            # fails OPEN (visible), not closed (see expression_eval.py's
            # sibling logic in retrieval/engine.py).
      }

    Facts are identified by canonical_name, not AI-DND's own entity_id
    (direct_authoring.py's identifier note) -- Core API is expected to
    resolve its own entity_id references to canonical_name before calling
    this, since it already holds that mapping.
    """

    scenario_id: UUID
    mode: Literal["newbie", "master"]
    world_data: dict[str, Any] = Field(default_factory=dict)


class ScenarioTemplateRequest(BaseModel):
    """Body for the AI-DND memory-layer contract's own proposed path,
    `POST /v1/memory/scenario/{scenario_id}/template` -- identical to
    `MemoryTemplateIngestRequest` except `scenario_id` comes from the URL,
    not the body."""

    mode: Literal["newbie", "master"]
    world_data: dict[str, Any] = Field(default_factory=dict)


class MemoryTemplateIngestResponse(BaseModel):
    """`template_space_id` echoes `scenario_id` -- mem1's real internal key
    is a derived string (`scenario-template::{scenario_id}`), but since it's
    always deterministically re-derivable from `scenario_id` alone, echoing
    the UUID the caller already has avoids a UUID/str contract mismatch
    (the kind `Fact.fact_id`/`batch_id` already have -- see the bridge plan)
    without inventing a second lookup the caller would need to store."""

    template_space_id: UUID


class MemoryTemplateCloneRequest(BaseModel):
    """`playthrough_id` here and in the URL path must agree when both are
    given; the path value is authoritative if a caller only has one."""

    scenario_id: UUID
    playthrough_id: UUID


class MemoryTemplateCloneResponse(BaseModel):
    """Echoes `playthrough_id`, same reasoning as `template_space_id` above."""

    playthrough_space_id: UUID


# §11 fix: rollback (`ingestion.rollback.RollbackService`) previously had no
# API surface at all -- reachable only from Python callers holding a
# `MemoryEngine` instance directly. These give it the same external-access
# shape every other mem1 capability already has.
class CreateSavePointRequest(BaseModel):
    session_id: str | None = None
    label: str | None = None


class SavePointResponse(BaseModel):
    save_id: str
    context_id: str
    session_id: str | None = None
    label: str | None = None
    created_at: datetime


class RollbackResponse(BaseModel):
    save_id: str
    archived_fact_ids: list[str]
    restored_fact_ids: list[str]


class AgentTurnRequest(BaseModel):
    """§11 fix: the first request shape that actually drives
    `MemoryEngine.agent_turn` (the tool-loop harness) -- see
    `core/agent_tools.py` for what the model can do with it."""

    context_id: str
    user_prompt: str
    system_prompt: str | None = None


class AgentTurnResponse(BaseModel):
    reply: str


class EntityDetailResponse(BaseModel):
    """AI-DND memory-layer contract §4.5: `GET /v1/memory/entity/{entity_id}`.
    `entity_id` in the path is mem1's `canonical_name` -- see
    `MemoryEngine.get_entity`'s docstring for the identifier-scheme
    reasoning."""

    entity_id: str
    canonical_name: str
    entity_type: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
