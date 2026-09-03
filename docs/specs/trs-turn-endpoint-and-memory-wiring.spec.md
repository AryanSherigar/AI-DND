# Spec: TRS `POST /v1/turn` Endpoint + Memory Retrieval/Write Wiring

## 1. Objective & User Outcome
- **Problem Statement:** `docs/specs/turn-resolution-pipeline.spec.md` built `pipeline.run_turn(...)` as a callable async function with a full, tested step sequence (`request_receiver → state_loader → ai_orchestrator → state_writer → response_streamer`), but explicitly deferred its HTTP entrypoint (`routers/turn.py` is a 0-byte file, not mounted in `main.py`) and memory-layer wiring (`context_retrieval.py`, `memory_writer.py` are 0-byte files, not called from the pipeline). As a result, no player action can reach TRS over the network at all — `pipeline.run_turn` is exercised only by tests. Separately, `apps/turn-resolution-service/app/integrations/gemini_client.py` has since been implemented for real (Vertex AI via the `google-genai` SDK, not the mock the earlier spec assumed) — this spec does not touch that file, it's already correct.
- **User Story:** As a player mid-playthrough, I want to POST my action to the live TRS API and see Gemini's narration stream back token-by-token, with retrieved world facts (from the still-mocked memory layer) informing the narration and my turn's text eventually queued for the memory layer's batched ingestion — so the "mock memory layer stays mocked, everything else works" goal is actually true end-to-end.
- **Success Criteria:**
  - `POST /v1/turn` exists, is mounted, and drives `pipeline.run_turn(...)` to a real SSE response over HTTP.
  - `context_retrieval.py` calls the existing mock `memory_client.query_memory(...)` before the Gemini call, and the orchestrator's prompt includes whatever facts (or the abstention) it returns.
  - `memory_writer.py` calls the existing mock `memory_client.ingest_batch(...)` roughly every 5 turns (per RFC ADR-5 / Open-4, resolved here as a fixed `turn_count % 5 == 0` trigger), never blocking or failing the turn if the mock ingest fails.
  - The memory layer itself remains fully mocked — no real mem1 network calls are introduced anywhere in this spec.

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **Router (`app/routers/turn.py`, filled in):** `POST /v1/turn`. Parses `TurnRequestInput` from the request body, resolves the current user via existing auth middleware, calls `pipeline.run_turn(...)`, returns the `EventSourceResponse` directly (FastAPI streams it).
  - **`app/main.py` (modified):** registers the new router: `app.include_router(turn.router)`.
  - **`app/turn/steps/context_retrieval.py` (filled in):** builds a `MemoryQueryRequest` from `TurnRequest`/`LoadedState` (per `app/models/memory.py`'s existing shape) and calls `memory_client.query_memory(...)`. Returns the `MemoryQueryResponse` (facts list + abstention flag) for the orchestrator to use.
  - **`app/turn/steps/ai_orchestrator.py` (modified):** `_build_prompt` gains the retrieved facts as an additional context block. If `abstained` is true, that block is simply omitted — never a special-cased error path, matching the RFC's framing of abstention as a normal signal.
  - **`app/turn/steps/memory_writer.py` (filled in):** after a successful `state_writer.write_turn(...)`, checks `new_turn_count % memory_batch_turn_interval == 0` (new config constant, default `5`). If true, builds a `MemoryIngestRequest` from the last `memory_batch_turn_interval` turns in `state.narrative.turns_so_far` and calls `memory_client.ingest_batch(...)`. Failures are caught and logged, never raised — per RFC's "memory batch failure never blocks the player."
  - **`app/turn/pipeline.py` (modified):** sequences `context_retrieval` between `state_loader` and `ai_orchestrator`, and `memory_writer` after a successful `state_writer.write_turn(...)` call, inside `_run_turn_events`. `pipeline.py` remains the only file that knows this order (CLAUDE.md).
  - **`app/config.py` (modified):** add `memory_batch_turn_interval: int = 5`.
  - **Explicitly out of scope (unchanged from the prior spec):** `condition_evaluator.py`, `tool_handler.py`, `state_validator.py`, `app/models/game_state.py`, `app/models/tool_call.py` — master-mode only, not needed for newbie mode, stay empty. `session/notification_manager.py`, `session/spectator_manager.py`, `routers/session.py` — covered by `docs/specs/sharing-and-multiplayer.spec.md`, not this one.

- **Sequence Flow (`POST /v1/turn`):**
  1. Client sends `{playthrough_id, participant_id, action_text}` with an auth token.
  2. `routers/turn.py` validates the user is authenticated (existing `middleware/auth.py`), passes the body straight to `pipeline.run_turn(...)` — no business logic in the router (CLAUDE.md's Router → Service/Pipeline rule).
  3. `request_receiver` / `state_loader` run exactly as already built.
  4. **New:** `context_retrieval.retrieve_context(turn_request, loaded_state, memory_client)` calls the mock `query_memory(...)` with `query_text=turn_request.action_text`, `checkpoint=loaded_state.checkpoint or ""`, `game_state=loaded_state.state`. Returns facts/abstention.
  5. `ai_orchestrator.generate_narration(...)` now also takes the retrieved context and folds it into `_build_prompt` as a `"Known world facts: ..."` block (or omits the block entirely on abstention).
  6. Narration streams exactly as already built; `state_writer.write_turn(...)` persists the turn.
  7. **New:** on successful persistence, `memory_writer.maybe_flush_batch(...)` runs. It never affects the SSE stream's `done`/`degraded` outcome — it's fire-and-forget from the client's perspective (its own failures are swallowed and logged, not surfaced as a stream event, matching the RFC's "low-key, in-fiction-appropriate notice" being reserved for a *combined* 10-turn catch-up failure, which is out of scope here — this spec implements only the single-batch trigger, not the 10-turn catchup-on-failure described in ADR-5. That catchup logic is a natural §6 follow-on, not built here).
  8. `response_streamer` emits `done` (or `degraded`) exactly as before — the memory write never changes this outcome.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Test:** `cd apps/turn-resolution-service && pytest tests/turn/ tests/routers/ -v`
- **Lint / Format:** `cd apps/turn-resolution-service && ruff format . && ruff check . --fix`
- **Full regression:** `cd apps/turn-resolution-service && pytest -v`
- **Manual smoke test:** `curl -N -X POST http://localhost:8001/v1/turn -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"playthrough_id": "...", "participant_id": "...", "action_text": "I look around."}'` — confirm `narration` events stream progressively, followed by `done`.

### 3.2. Testing Strategy & Conformance
- **Location:** `apps/turn-resolution-service/tests/turn/steps/test_context_retrieval.py`, `test_memory_writer.py` (new); `apps/turn-resolution-service/tests/routers/test_turn.py` (new); `apps/turn-resolution-service/tests/turn/test_pipeline.py` (extended).
- **Framework:** `pytest-asyncio`. Unit tests mock `memory_client` (already a mock module — tests control its return values directly, same pattern as `test_ai_orchestrator.py` mocking `gemini_client`). The router/pipeline integration tests run against real test Postgres, per CLAUDE.md.
- **Deterministic test cases:**
  1. `context_retrieval`: happy path — mocked `query_memory` returns facts → returned to caller unchanged.
  2. `context_retrieval`: abstention — mocked `query_memory` returns `abstained=True` → orchestrator receives an empty/absent fact list, no error raised.
  3. `ai_orchestrator`: prompt includes a facts block when facts are present; prompt omits it entirely on abstention (assert on the built prompt string, not the network call).
  4. `memory_writer`: `new_turn_count == 5` → `ingest_batch` called once with the last 5 turns.
  5. `memory_writer`: `new_turn_count == 4` or `6` → `ingest_batch` not called (off-by-one guard, mirrors the `play_count` boundary test in the prior spec).
  6. `memory_writer`: mocked `ingest_batch` raises → exception is caught, logged, does not propagate — turn's SSE stream still emits `done`.
  7. `routers/test_turn.py`: `POST /v1/turn` with a valid seeded playthrough/participant → `200`, `text/event-stream` content type, response body contains `event: narration` and `event: done` markers.
  8. `routers/test_turn.py`: unauthenticated request → `401` before any pipeline code runs.
  9. Pipeline integration (extended from the prior spec's test): assert `context_retrieval` and `memory_writer` are both invoked in the correct order relative to `ai_orchestrator`/`state_writer` (e.g. via a call-order spy on the mocked `memory_client`).

### 3.3. Project Structure & File Layout
- **Files created:**
  - `apps/turn-resolution-service/tests/turn/steps/test_context_retrieval.py`
  - `apps/turn-resolution-service/tests/turn/steps/test_memory_writer.py`
  - `apps/turn-resolution-service/tests/routers/test_turn.py`
- **Files filled in (previously empty stubs):**
  - `apps/turn-resolution-service/app/routers/turn.py`
  - `apps/turn-resolution-service/app/turn/steps/context_retrieval.py`
  - `apps/turn-resolution-service/app/turn/steps/memory_writer.py`
- **Files modified:**
  - `apps/turn-resolution-service/app/turn/pipeline.py` — wire in the two new steps.
  - `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py` — accept and render retrieved context in `_build_prompt`.
  - `apps/turn-resolution-service/app/main.py` — `app.include_router(turn.router)`.
  - `apps/turn-resolution-service/app/config.py` — add `memory_batch_turn_interval`.
  - `apps/turn-resolution-service/app/models/turn.py` — extend `LoadedState`/add a small `RetrievedContext` shape if needed for the step boundary.
- **Files explicitly NOT touched:** `condition_evaluator.py`, `tool_handler.py`, `state_validator.py`, `app/models/game_state.py`, `app/models/tool_call.py`, `app/routers/session.py`, `app/session/*` (all covered elsewhere or out of scope).

### 3.4. Code Style & Interfaces

**`app/routers/turn.py`:**
```python
"""FastAPI router for the live turn-resolution endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.connection import get_db_session
from app.middleware.auth import get_current_user
from app.models.turn import TurnRequestInput
from app.turn.pipeline import run_turn

router = APIRouter(prefix="/v1/turn", tags=["Turn"])


@router.post("", response_model=None)
async def submit_turn(
    turn_input: TurnRequestInput,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[object, Depends(get_current_user)],
) -> EventSourceResponse:
    """Submit a player action and stream back narration over SSE."""
    return await run_turn(turn_input, session)
```

**`app/turn/steps/context_retrieval.py`:**
```python
"""Retrieves grounded world facts from the (mocked) memory layer for a turn."""

from app.integrations import memory_client
from app.models.memory import MemoryQueryRequest, MemoryQueryResponse
from app.models.turn import LoadedState, TurnRequest


async def retrieve_context(
    turn_request: TurnRequest, loaded_state: LoadedState
) -> MemoryQueryResponse:
    """Query the memory layer for facts relevant to this turn's action."""
    request = MemoryQueryRequest(
        scenario_id=loaded_state.scenario_id,
        playthrough_id=turn_request.playthrough_id,
        participant_id=turn_request.participant_id,
        query_text=turn_request.action_text,
        checkpoint=loaded_state.checkpoint or "",
        game_state=loaded_state.state,
        as_of_turn=loaded_state.turn_count,
    )
    return await memory_client.query_memory(request)
```

**`app/turn/steps/memory_writer.py`:**
```python
"""Batches recent turns to the (mocked) memory layer roughly every N turns.

Failures here are swallowed and logged, never raised: per RFC ADR-5 and the
Data Consistency section, memory writes are best-effort and must never block
or fail a turn.
"""

import logging

from app.config import settings
from app.integrations import memory_client
from app.models.memory import MemoryIngestRequest, TurnBatchEntry
from app.models.turn import LoadedState, TurnRequest

logger = logging.getLogger(__name__)


async def maybe_flush_batch(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    new_turn_count: int,
    updated_turns_so_far: list[dict[str, object]],
) -> None:
    """Fire a batched ingest to the memory layer if this turn hits the interval."""
    if new_turn_count % settings.memory_batch_turn_interval != 0:
        return

    batch = updated_turns_so_far[-settings.memory_batch_turn_interval :]
    request = MemoryIngestRequest(
        scenario_id=loaded_state.scenario_id,
        playthrough_id=turn_request.playthrough_id,
        turns_batch=[
            TurnBatchEntry(
                turn_number=new_turn_count - len(batch) + i + 1,
                text=f"{t['action_text']} -> {t['narration_text']}",
                participant_id=turn_request.participant_id,
            )
            for i, t in enumerate(batch)
        ],
    )
    try:
        await memory_client.ingest_batch(request)
    except Exception:
        logger.warning("Memory batch ingest failed for playthrough %s", turn_request.playthrough_id, exc_info=True)
```

**`app/turn/pipeline.py` (`_run_turn_events`, modified excerpt):**
```python
context = await context_retrieval.retrieve_context(turn_request, loaded_state)

chunks: list[str] = []
async for chunk in ai_orchestrator.generate_narration(turn_request, loaded_state, context):
    chunks.append(chunk)
    yield response_streamer.narration_event(chunk)

narration_text = "".join(chunks)
updated_turns = await state_writer.write_turn(...)  # returns updated_turns_so_far
await memory_writer.maybe_flush_batch(turn_request, loaded_state, loaded_state.turn_count + 1, updated_turns)
yield response_streamer.done_event()
```
`state_writer.write_turn` needs a small signature change to return the updated `turns_so_far` list (or the full updated state) rather than `None`, so `memory_writer` doesn't have to recompute it — keep this a pure return-value change, not a new I/O call.

### 3.5. Git & Review Workflow
- **Branch name:** `feat/trs-turn-endpoint-memory-wiring`
- **Commit scope:** router + main.py in one commit, context_retrieval + ai_orchestrator prompt change in another, memory_writer + pipeline wiring + config in a third, tests can accompany each.
- **PR validation checklist:**
  - [ ] `ruff format --check .` and `ruff check .` clean
  - [ ] `POST /v1/turn` reachable and streams progressively (manual curl test in §3.1)
  - [ ] `memory_writer` never raises past its own try/except — grep for the swallow
  - [ ] `pipeline.py` remains the only file sequencing steps — steps still don't import each other directly

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** keep the memory layer mocked — no real HTTP calls to `MEMORY_SERVICE_URL` or any external mem1 endpoint anywhere in this spec; keep `memory_writer` failures non-fatal to the turn.
- ⚠️ **Ask First:** implementing the RFC's 10-turn catchup-on-failure batching logic (ADR-5) — this spec only implements the single 5-turn trigger, not the catchup; implementing checkpoint advancement.
- 🚫 **Never:** let `context_retrieval` or `memory_writer` block/fail the turn on a memory-layer error; let `ai_orchestrator` call `memory_client` directly (only `context_retrieval`/`memory_writer` may).

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Memory query abstains or the mock is momentarily "down":** narration proceeds without the facts block — never a player-visible error, matching the RFC's abstention framing exactly.
- **Memory ingest batch fails:** logged, swallowed, turn still completes normally from the player's perspective; the RFC's 10-turn catchup is explicitly deferred (§3.6 "Ask First"), so a single failed batch is simply lost in this pass — acceptable per the mock-only scope, revisit if a real memory layer is ever wired in.
- **Turn count crosses the batch interval more than once in fast succession (can't currently happen, single write per turn):** the `%` check is idempotent per turn, same invariant style as the `play_count` boundary check in the prior spec.
- **Unauthenticated `POST /v1/turn`:** rejected by `get_current_user` before the pipeline runs — no wasted Gemini or memory calls.

## 5. Phased Implementation Tasks (Task Checklist)
- [x] **Task 1 (Router + mount):** `app/routers/turn.py`, `app/main.py` registration. **Blocker found and fixed:** `middleware/auth.py` only allowed the `x-dev-user-id` bypass under `environment == "development"`, but tests (and this router) run under `environment == "testing"` — same gap Core API's auth middleware already handles. Brought TRS's middleware in line (accept `"testing"` too, and return a proper 401 via `InvalidTokenError` for a missing token instead of FastAPI's default 403 from `HTTPBearer()`). Verified with a manual curl smoke test against a seeded playthrough — confirmed the request reaches auth → `request_receiver` → `state_loader` → `context_retrieval` (the mock memory call) → `ai_orchestrator` correctly; the only failure past that point is the real Gemini SDK having no local Vertex AI credentials in this sandbox, which is outside this spec's scope (`gemini_client.py` untouched).
- [x] **Task 2 (Context retrieval):** `context_retrieval.py` + `ai_orchestrator.py` prompt change (added `_build_facts_block`). `test_context_retrieval.py` (3 tests) and extended `test_ai_orchestrator.py` (2 new facts-block tests, 3 existing tests updated for the new `context` parameter) all pass.
- [x] **Task 3 (Memory writer + pipeline wiring):** `memory_writer.py`, `pipeline.py` wiring, `state_writer.write_turn` now returns the updated `turns_so_far` list, `config.py` addition (`memory_batch_turn_interval`). `test_memory_writer.py` (4 tests) passes.
- [x] **Task 4 (Router integration test):** `tests/routers/test_turn.py` against real Postgres — added an `async_client` fixture to `tests/conftest.py` (TRS had none before, mirroring Core API's pattern) to make this possible. 2/2 pass.
- [x] **Task 5 (Full regression):** `pytest -v` — 54/54 pass (0 before this spec's new tests, i.e. no regressions in the 40 pre-existing tests). `ruff format .` and `ruff check .` clean across the whole service.
