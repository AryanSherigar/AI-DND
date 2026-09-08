from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from uuid import UUID, uuid5

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.models import (
    AgentTurnRequest,
    AgentTurnResponse,
    CreateSavePointRequest,
    EntityDetailResponse,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryQueryRequest,
    MemoryQueryResponse,
    MemoryTemplateCloneRequest,
    MemoryTemplateCloneResponse,
    MemoryTemplateIngestRequest,
    MemoryTemplateIngestResponse,
    RollbackRequest,
    RollbackResponse,
    SavePointResponse,
    ScenarioTemplateRequest,
)
from api.models import BatchStatus as MemoryBatchStatus
from api.models import Fact as MemoryFact
from api.stream import streamer
from context_memory.engine import MemoryEngine
from context_memory.ingestion.batch_models import (
    TurnBatchEntry as DomainTurnBatchEntry,
)
from context_memory.ingestion.batch_models import (
    dedupe_turn_entries,
)
from context_memory.ingestion.direct_authoring import DirectEntityInput, DirectFactInput
from context_memory.ingestion.rollback import SavePointOwnershipError


def get_engine(request: Request) -> MemoryEngine:
    """HIGH-01 fix: the engine is built exactly once, in `lifespan`
    (api/server.py), and stashed on `app.state.engine`. Routes must read
    that instance rather than lazily building a second one -- see the
    memory-layer audit's HIGH-01 finding for the duplicate-engine bug this
    replaces."""
    return request.app.state.engine


router = APIRouter()


# §12 fix: opt-in bearer-token auth ("No API authentication"). Off by
# default -- an unset CONTEXT_MEMORY_API_KEY preserves exactly today's
# fully-open behavior, so this can never break an existing deployment or
# test that hasn't configured it. Set the env var to require every request
# through this router to present `Authorization: Bearer <key>`; wired at
# the app level (api/server.py's `app.include_router(router,
# dependencies=[Depends(require_api_key)])`), not per-route, so a new
# route added later is covered automatically rather than by remembering to
# opt each one in.
def require_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("CONTEXT_MEMORY_API_KEY")
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid API key")


class SearchRequest(BaseModel):
    context_id: str
    query: str
    question_date: datetime | None = None
    scenario_id: str | None = None


class ChatRequest(BaseModel):
    context_id: str
    session_id: str
    user_message: str
    scenario_id: str | None = None


@router.post(
    "/v1/memory/ingest",
    response_model=MemoryIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_memory(
    req: MemoryIngestRequest, engine: MemoryEngine = Depends(get_engine)
) -> MemoryIngestResponse:
    """Async batched ingest for AI-DND's Turn Resolution Service (Milestone 2
    of the AI-DND bridge). `playthrough_id` is mem1's `context_id`. Returns
    immediately with a `batch_id` -- poll `GET /v1/memory/batch/{batch_id}/status`
    for completion, per ADR-5 (memory writes never block a turn)."""
    to_domain = lambda t: DomainTurnBatchEntry(
        turn_number=t.turn_number,
        text=t.text,
        participant_id=str(t.participant_id),
        occurred_at=t.occurred_at,
    )
    entries = dedupe_turn_entries(
        (to_domain(t) for t in req.turns_batch),
        (to_domain(t) for t in req.recent_context_turns),
    )
    batch_id = engine.submit_batch(str(req.playthrough_id), entries)
    return MemoryIngestResponse(batch_id=batch_id)


@router.get("/v1/memory/batch/{batch_id}/status", response_model=MemoryBatchStatus)
def get_batch_status(
    batch_id: str, engine: MemoryEngine = Depends(get_engine)
) -> MemoryBatchStatus:
    # §3 fix: an unknown batch_id (never submitted, or submitted to a
    # different replica/before a restart with no durable trace) now raises
    # BatchNotFoundError instead of reporting "pending" forever.
    try:
        result = engine.get_batch_status(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return MemoryBatchStatus(
        batch_id=result.batch_id,
        status=result.status,
        facts_created=result.facts_created,
        error=result.error,
        retryable=result.retryable,
    )


@router.post("/v1/memory/batch/{batch_id}/retry", response_model=MemoryIngestResponse)
def retry_batch(
    batch_id: str, engine: MemoryEngine = Depends(get_engine)
) -> MemoryIngestResponse:
    try:
        engine.retry_batch(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return MemoryIngestResponse(batch_id=batch_id)


@router.post("/v1/memory/search")
def search_memory(req: SearchRequest, engine: MemoryEngine = Depends(get_engine)):
    q_date = req.question_date or datetime.now(UTC)
    answer = engine.search_memories(req.context_id, req.query, q_date, req.scenario_id)
    return {"answer": answer}


_FACT_ID_NAMESPACE = UUID("69405270-4408-4292-924a-a8d139303566")


def _stable_fact_uuid(fact_id: str) -> str:
    """Fallback ONLY for facts with no caller-assigned `external_fact_id`
    (autonomously extracted facts -- see NEW-CRIT-01). mem1's internal
    `fact_id` is a bare graph_id (`"142"`) or a `fact:direct:<hash>`
    logical key -- neither parses as a UUID, but AI-DND's real (non-mock)
    `Fact.fact_id` field is typed `UUID` (`apps/*/app/models/memory.py`).
    One-way deterministic derivation is safe here: this synthetic id is
    never sent back into any mem1 endpoint as input. A fact carrying a real
    `external_fact_id` uses that instead (`query_memory`), so it round-trips
    correctly against `revealed_facts`/`superseded_fact_id` comparisons."""
    return str(uuid5(_FACT_ID_NAMESPACE, fact_id))


@router.post("/v1/memory/query", response_model=MemoryQueryResponse)
def query_memory(
    req: MemoryQueryRequest, engine: MemoryEngine = Depends(get_engine)
) -> MemoryQueryResponse:
    """Structured retrieval for AI-DND's Turn Resolution Service (Milestones
    1, 4, 5 of the bridge). `playthrough_id` is mem1's `context_id`;
    `template_context_id` (derived from `scenario_id`, never stored per-
    playthrough) is where Milestone 5's checkpoint ordering lives -- see the
    identifier mapping in the bridge plan.
    """
    question_date = datetime.now(UTC)
    result = engine.retrieve_facts(
        context_id=str(req.playthrough_id),
        query_text=req.query_text,
        question_date=question_date,
        game_state=req.game_state,
        checkpoint=req.checkpoint,
        as_of_turn=req.as_of_turn,
        template_context_id=_template_context_id(req.scenario_id),
        # §5 fix: both were accepted on the wire and silently dropped here.
        participant_id=str(req.participant_id),
        scenario_id=str(req.scenario_id),
    )
    facts = [
        MemoryFact(
            # NEW-CRIT-01 fix: prefer the caller's own authored id (set via
            # direct authoring's `external_fact_id`) so TRS's
            # `revealed_fact_ids` comparison can actually match -- only
            # facts with no authored id (autonomously extracted) keep the
            # synthetic uuid5 derivation.
            fact_id=f.external_fact_id or _stable_fact_uuid(f.fact_id),
            subject=f.subject,
            predicate=f.predicate,
            object=f.object,
            valid_from=f.valid_from,
            valid_until=f.valid_until,
            confidence=f.confidence,
            hidden=f.hidden,
            when_active=f.when_active,
        )
        for f in result.facts
    ]
    return MemoryQueryResponse(
        facts=facts,
        abstained=result.abstained,
        resolved_time_point=result.resolved_time_point,
    )


def _template_context_id(scenario_id: UUID) -> str:
    """Deterministic, never stored: both `ingest_scenario_template` and
    `clone_template_memory_space` re-derive the same string from
    `scenario_id` alone, so the wire contract never needs to carry mem1's
    internal context_id key at all (see MemoryTemplateIngestResponse's
    docstring in api/models.py)."""
    return f"scenario-template::{scenario_id}"


def _parse_template_entity(raw: dict) -> DirectEntityInput:
    return DirectEntityInput(
        canonical_name=raw["canonical_name"],
        entity_type=raw["entity_type"],
        aliases=tuple(raw.get("aliases") or ()),
        description=raw.get("description"),
    )


def _parse_template_fact(raw: dict) -> DirectFactInput:
    valid_from = raw.get("valid_from")
    return DirectFactInput(
        predicate=raw["predicate"],
        subject_canonical_name=raw["subject_canonical_name"],
        object_canonical_name=raw.get("object_canonical_name"),
        object_literal=raw.get("object_literal"),
        valid_from=datetime.fromisoformat(valid_from) if valid_from else None,
        when_active=raw.get("when_active"),
        checkpoint=raw.get("checkpoint"),
        # §5 fix: optional participant-scoped visibility -- see
        # DirectFactInput's field comment.
        visible_to_participant_id=raw.get("visible_to_participant_id"),
        # AI-DND memory-layer contract: author-marked secret, and the
        # caller's own fact-id pair for supersession -- see
        # DirectFactInput's field comments.
        hidden=bool(raw.get("hidden", False)),
        external_fact_id=raw.get("external_fact_id"),
        superseded_fact_id=raw.get("superseded_fact_id"),
    )


def _ingest_scenario_template(
    scenario_id: UUID, mode: str, world_data: dict, engine: MemoryEngine
) -> MemoryTemplateIngestResponse:
    """Shared by both template-ingest routes below -- the doc's proposed
    path and mem1's own pre-existing one describe the exact same operation,
    just with `scenario_id` arriving from the path vs. the body."""
    context_id = _template_context_id(scenario_id)
    try:
        if mode == "newbie":
            lore_text = world_data.get("lore_text")
            if not lore_text:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "newbie mode requires world_data.lore_text",
                )
            engine.ingest_template_lore(context_id, lore_text)
        else:
            # AI-DND memory-layer contract: a republish must replace prior
            # content, not accumulate alongside it -- see
            # `begin_template_republish`'s own docstring for what this
            # closes (a real gap found while scoping the upsert
            # requirement, not asked for directly).
            engine.begin_template_republish(context_id)
            for raw_entity in world_data.get("entities", []):
                engine.write_template_entity(
                    context_id, _parse_template_entity(raw_entity)
                )
            for raw_fact in world_data.get("facts", []):
                engine.write_template_fact(context_id, _parse_template_fact(raw_fact))
            checkpoints = world_data.get("checkpoints")
            if checkpoints:
                engine.write_scenario_checkpoints(context_id, list(checkpoints))
    except KeyError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"world_data missing required field: {e}"
        ) from e
    return MemoryTemplateIngestResponse(template_space_id=scenario_id)


@router.post("/v1/memory/template/ingest", response_model=MemoryTemplateIngestResponse)
def ingest_scenario_template(
    req: MemoryTemplateIngestRequest, engine: MemoryEngine = Depends(get_engine)
) -> MemoryTemplateIngestResponse:
    """Authoring-time ingestion at scenario publish (Milestone 3, ADR-7).
    Newbie mode runs the same LLM extractor runtime ingestion uses, pointed
    at the template context; master mode direct-writes, no LLM call --
    see `world_data`'s expected shape in api/models.py.

    mem1's own pre-existing path (`scenario_id` in the body). Kept
    alongside the AI-DND memory-layer contract's proposed path below rather
    than replaced -- this one is live and already exercised."""
    return _ingest_scenario_template(req.scenario_id, req.mode, req.world_data, engine)


@router.post(
    "/v1/memory/scenario/{scenario_id}/template",
    response_model=MemoryTemplateIngestResponse,
)
def ingest_scenario_template_by_path(
    scenario_id: UUID,
    req: ScenarioTemplateRequest,
    engine: MemoryEngine = Depends(get_engine),
) -> MemoryTemplateIngestResponse:
    """AI-DND memory-layer contract's own proposed path (`scenario_id` in
    the URL, not the body) -- added alongside `/v1/memory/template/ingest`
    rather than instead of it, since that's the path Core API's
    `publish_service.py` actually calls. Same operation, same semantics."""
    return _ingest_scenario_template(scenario_id, req.mode, req.world_data, engine)


@router.post(
    "/v1/memory/playthrough/{playthrough_id}/init",
    response_model=MemoryTemplateCloneResponse,
)
def init_playthrough_memory_space(
    playthrough_id: UUID,
    req: MemoryTemplateCloneRequest,
    engine: MemoryEngine = Depends(get_engine),
) -> MemoryTemplateCloneResponse:
    """ADR-7's clone step, triggered by Core API when it creates the
    Playthrough row. The path's `playthrough_id` is authoritative; the
    body's is expected to match (accepted for AI-DND's own
    `MemoryTemplateCloneRequest` shape) but never overrides it."""
    if req.playthrough_id != playthrough_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "playthrough_id in body must match the URL path",
        )
    template_context_id = _template_context_id(req.scenario_id)
    target_context_id = str(playthrough_id)
    engine.clone_playthrough_space(template_context_id, target_context_id)
    if req.player_entity_canonical_name:
        engine.write_template_entity(
            target_context_id,
            DirectEntityInput(
                canonical_name=req.player_entity_canonical_name,
                entity_type="character",
                aliases=tuple(req.player_entity_aliases or ()),
            ),
        )
    for raw_fact in req.setup_facts:
        engine.write_template_fact(target_context_id, _parse_template_fact(raw_fact))
    return MemoryTemplateCloneResponse(playthrough_space_id=playthrough_id)


@router.post("/v1/chat")
def chat_turn(req: ChatRequest, engine: MemoryEngine = Depends(get_engine)):
    reply = engine.generate_reply(
        req.context_id, req.session_id, req.user_message, req.scenario_id
    )
    return {"reply": reply}


# §11 fix: rollback (ingestion/rollback.py's RollbackService, wired into
# MemoryEngine as create_save_point/rollback_to) had no API surface at all
# before these two routes -- reachable only from Python callers holding a
# MemoryEngine instance directly.
@router.post("/v1/memory/{context_id}/save-point", response_model=SavePointResponse)
def create_save_point(
    context_id: str,
    req: CreateSavePointRequest,
    engine: MemoryEngine = Depends(get_engine),
) -> SavePointResponse:
    save_point = engine.create_save_point(context_id, req.session_id, req.label)
    return SavePointResponse(
        save_id=save_point.save_id,
        context_id=save_point.context_id,
        session_id=save_point.session_id,
        label=save_point.label,
        created_at=save_point.created_at,
    )


@router.post("/v1/memory/rollback/{save_id}", response_model=RollbackResponse)
def rollback_to_save_point(
    save_id: str,
    req: RollbackRequest,
    engine: MemoryEngine = Depends(get_engine),
) -> RollbackResponse:
    try:
        result = engine.rollback_to(save_id, req.context_id)
    except SavePointOwnershipError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return RollbackResponse(
        save_id=result.save_id,
        archived_fact_ids=list(result.archived_fact_ids),
        restored_fact_ids=list(result.restored_fact_ids),
    )


# §11 fix: the first request shape/route that actually calls the Phase 9
# tool harness (ToolRegistry/GuardedToolExecutor/run_tool_loop) -- see
# MemoryEngine.agent_turn and core/agent_tools.py.
@router.post("/v1/memory/agent", response_model=AgentTurnResponse)
def agent_turn(
    req: AgentTurnRequest, engine: MemoryEngine = Depends(get_engine)
) -> AgentTurnResponse:
    reply = engine.agent_turn(req.context_id, req.user_prompt, req.system_prompt)
    return AgentTurnResponse(reply=reply)


# AI-DND memory-layer contract §4.5 ("required for launch", not called by
# any product code today -- present in the RFC as a debugging/future-
# tool-calling hook). `entity_id` is mem1's `canonical_name` -- see
# MemoryEngine.get_entity's docstring.
@router.get("/v1/memory/entity/{entity_id}", response_model=EntityDetailResponse)
def get_entity(
    entity_id: str, context_id: str, engine: MemoryEngine = Depends(get_engine)
) -> EntityDetailResponse:
    entity = engine.get_entity(context_id, entity_id)
    if entity is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no entity {entity_id!r} in context {context_id!r}",
        )
    return EntityDetailResponse(**entity)


def _resolve_stream_context_id(
    context_id: str | None, playthrough_id: str | None
) -> str:
    """CRIT-01 fix: exactly one of `context_id`/`playthrough_id` (an
    alias for the same identifier -- see query_memory's docstring) must be
    given so the stream can be scoped to a single tenant."""
    if context_id and playthrough_id and context_id != playthrough_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "context_id and playthrough_id must match when both are given",
        )
    resolved = context_id or playthrough_id
    if not resolved:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "context_id (or playthrough_id) query parameter is required",
        )
    return resolved


# CRIT-01 fix: moved onto `router` (previously declared directly on `app`
# in server.py, bypassing `require_api_key`) and scoped to a single
# tenant's writes -- see GraphStreamer.add_queue/broadcast_plan.
@router.get("/v1/memory/stream")
async def stream_graph(
    request: Request,
    context_id: str | None = Query(default=None),
    playthrough_id: str | None = Query(default=None),
):
    resolved_context_id = _resolve_stream_context_id(context_id, playthrough_id)
    if streamer.loop is None:
        streamer.loop = asyncio.get_running_loop()

    q = streamer.add_queue(resolved_context_id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            streamer.remove_queue(resolved_context_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
    return EntityDetailResponse(**entity)


def _ping_postgres_pool(pool: object) -> None:
    with (
        pool.connection() as connection,  # type: ignore[attr-defined]
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT 1")


async def _check_postgres(request: Request, timeout_seconds: float = 0.5) -> str:
    # HIGH-01 fix: app.state.engine is the only engine instance now -- no
    # more _GLOBAL_ENGINE fallback to check.
    engine = getattr(request.app.state, "engine", None)
    if engine is None or not hasattr(engine, "pool") or engine.pool is None:
        return "down (uninitialized)"
    try:
        await asyncio.wait_for(
            asyncio.to_thread(_ping_postgres_pool, engine.pool),
            timeout=timeout_seconds,
        )
        return "up"
    except TimeoutError:
        return "down (TimeoutError)"
    except Exception as exception:  # noqa: BLE001
        return f"down ({type(exception).__name__})"


async def _check_hydradb(timeout_seconds: float = 0.5) -> str:
    hydra_url = os.environ.get(
        "CONTEXT_MEMORY_HYDRADB_URL",
        os.environ.get("HYDRA_DB_HOST", "http://127.0.0.1:8080"),
    )
    if not hydra_url.startswith("http://") and not hydra_url.startswith("https://"):
        hydra_url = f"http://{hydra_url}"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{hydra_url}/health")
            return (
                "up"
                if response.status_code < 500
                else f"unhealthy ({response.status_code})"
            )
    except Exception as exception:  # noqa: BLE001
        return f"down ({type(exception).__name__})"


@router.get("/v1/health")
async def health_check(request: Request) -> dict[str, str]:
    postgres_status, hydradb_status = await asyncio.gather(
        _check_postgres(request),
        _check_hydradb(),
    )
    is_healthy = postgres_status == "up" and hydradb_status == "up"
    overall_status = "ok" if is_healthy else "degraded"
    return {
        "status": overall_status,
        "postgres": postgres_status,
        "hydradb": hydradb_status,
    }


@router.post("/v1/demo/clear")
def clear_demo():
    from api.stream import streamer

    streamer.push_event({"type": "graph_clear"})
    return {"status": "cleared"}


@router.post("/v1/demo/simulate")
async def simulate_demo(background_tasks: BackgroundTasks):
    from api.stream import streamer

    async def run_simulation():
        streamer.push_event({"type": "graph_clear"})
        await asyncio.sleep(0.3)

        streamer.push_event(
            {
                "type": "chat_message",
                "message": {
                    "id": f"demo-{int(time.time() * 1000)}-1",
                    "role": "user",
                    "content": "Hi! My name is Alice, and I am a Principal AI Engineer at TechCorp.",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        )
        await asyncio.sleep(0.6)

        streamer.push_event(
            {
                "type": "graph_update",
                "nodes": [
                    {
                        "id": "node-alice",
                        "label": "Entity",
                        "properties": {"name": "Alice"},
                    },
                    {
                        "id": "node-techcorp",
                        "label": "Entity",
                        "properties": {"name": "TechCorp"},
                    },
                    {
                        "id": "node-role",
                        "label": "Fact",
                        "properties": {"name": "Principal AI Engineer"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source_id": "node-alice",
                        "target_id": "node-techcorp",
                        "type": "WORKS_AT",
                    },
                    {
                        "id": "edge-2",
                        "source_id": "node-alice",
                        "target_id": "node-role",
                        "type": "HAS_ROLE",
                    },
                ],
            }
        )
        await asyncio.sleep(1.0)

        streamer.push_event(
            {
                "type": "chat_message",
                "message": {
                    "id": f"demo-{int(time.time() * 1000)}-2",
                    "role": "agent",
                    "content": "Hello Alice! Great to meet you. I've stored your role at TechCorp in long-term memory.",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        )
        await asyncio.sleep(1.0)

        streamer.push_event(
            {
                "type": "chat_message",
                "message": {
                    "id": f"demo-{int(time.time() * 1000)}-3",
                    "role": "user",
                    "content": "I prefer dark mode UI and love drinking Matcha Latte during code reviews.",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        )
        await asyncio.sleep(0.6)

        streamer.push_event(
            {
                "type": "graph_update",
                "nodes": [
                    {
                        "id": "node-alias-alice",
                        "label": "Alias",
                        "properties": {"name": "Alice_Alias"},
                    },
                    {
                        "id": "node-darkmode",
                        "label": "Fact",
                        "properties": {"name": "Prefers Dark Mode"},
                    },
                    {
                        "id": "node-matcha",
                        "label": "Fact",
                        "properties": {"name": "Loves Matcha Latte"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-3",
                        "source_id": "node-alice",
                        "target_id": "node-alias-alice",
                        "type": "HAS_ALIAS",
                    },
                    {
                        "id": "edge-4",
                        "source_id": "node-alice",
                        "target_id": "node-darkmode",
                        "type": "PREFERS",
                    },
                    {
                        "id": "edge-5",
                        "source_id": "node-alice",
                        "target_id": "node-matcha",
                        "type": "LIKES",
                    },
                ],
            }
        )
        await asyncio.sleep(1.0)

        streamer.push_event(
            {
                "type": "chat_message",
                "message": {
                    "id": f"demo-{int(time.time() * 1000)}-4",
                    "role": "agent",
                    "content": "Noted! Preferences for Dark Mode and Matcha Latte saved to your memory profile.",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        )
        await asyncio.sleep(1.0)

        streamer.push_event(
            {
                "type": "chat_message",
                "message": {
                    "id": f"demo-{int(time.time() * 1000)}-5",
                    "role": "user",
                    "content": "Recently moved from San Francisco to Neo-Tokyo.",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        )
        await asyncio.sleep(0.6)

        streamer.push_event(
            {
                "type": "graph_update",
                "nodes": [
                    {
                        "id": "node-neotokyo",
                        "label": "Entity",
                        "properties": {"name": "Neo-Tokyo"},
                    },
                    {
                        "id": "node-turn-3",
                        "label": "Turn",
                        "properties": {"name": "Session Turn 3"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-6",
                        "source_id": "node-alice",
                        "target_id": "node-neotokyo",
                        "type": "LIVES_IN",
                    },
                    {
                        "id": "edge-7",
                        "source_id": "node-neotokyo",
                        "target_id": "node-turn-3",
                        "type": "LOCATED_AT",
                    },
                ],
            }
        )

    background_tasks.add_task(run_simulation)
    return {"status": "simulation_started"}
