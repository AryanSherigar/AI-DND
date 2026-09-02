# Spec: TRS Turn Pipeline (`pipeline.py` + Core Steps)

## 1. Objective & User Outcome
- **Problem Statement:** `apps/turn-resolution-service/` exists only as scaffolding — every file the turn pipeline needs (`app/turn/pipeline.py`, all of `app/turn/steps/*.py`, `app/integrations/gemini_client.py`, `app/models/turn.py`, `app/exceptions/turn_exceptions.py`) is a 0-byte stub. Core API's playthrough-creation flow is fully built and already produces everything TRS needs to act on: a `Playthrough` row with a frozen `scenario_snapshot` (ADR-8) and a seeded newbie-mode `state`. Nothing yet turns a player's submitted action into narration, and nothing persists a turn. This is the next load-bearing piece of the core product loop.
- **User Story:** As a player mid-playthrough, I want to submit an action and receive streamed AI narration in response, with my turn durably recorded, so that the story continues and I can keep playing without losing progress if something goes wrong mid-generation.
- **Success Criteria:**
  - A validated turn request produces a Gemini-generated narration streamed to the client token-by-token (never buffered), and only after generation succeeds and the write is durable does the client see completion.
  - `Playthrough.state`, `turn_count`, and a new `TurnLog` row are updated atomically with respect to the stream: a client never sees `done` for a turn that wasn't actually persisted.
  - `Scenario.play_count` is incremented exactly once, only at `turn_count == 10`, and TRS touches no other `Scenario` field (hard constraint from `CLAUDE.md`).
  - Gemini timeouts and Postgres write failures degrade gracefully (retry, then an in-stream notice) rather than silently failing or corrupting state.
  - This scope is explicitly **newbie-mode only**: no Gemini tool-calling, no state-mutation validation, no memory-layer retrieval, no active-condition evaluation. These are real, separately-scoped follow-on work (see §6), not implicit gaps.

## 2. Technical Architecture & Data Flow

- **Components Involved:**
  - **Pipeline (`app/turn/pipeline.py`, new):** the only file that knows step order. Exposes one async entrypoint that a future router spec will call; steps never call each other directly.
  - **Steps (`app/turn/steps/`, new):** `request_receiver.py`, `state_loader.py`, `ai_orchestrator.py`, `state_writer.py`, `response_streamer.py`. `condition_evaluator.py`, `context_retrieval.py`, `tool_handler.py`, `state_validator.py`, `memory_writer.py` remain empty stubs — **not called, not even as no-ops** — this pipeline sequences only the five files above.
  - **Repositories (`app/repositories/`, new — this directory doesn't exist in TRS yet):** `playthrough_repo.py`, `turn_log_repo.py`, `participant_repo.py`, `scenario_repo.py`. Introduced here specifically because CLAUDE.md mandates SQL only lives in `repositories/` and TRS currently has no such layer; without it `state_loader.py`/`state_writer.py` would have to touch the DB session directly, violating the Router → Service → Repository → Database rule.
  - **Gemini client (`app/integrations/gemini_client.py`, new, mock):** the only file `ai_orchestrator.py` may call into. Follows the exact phased-mock pattern already established by `app/integrations/memory_client.py` (its docstring explicitly frames itself as swappable for the real client later with zero caller changes) — real Vertex AI SDK wiring is out of scope here.
  - **Models (`app/models/turn.py`, `app/exceptions/turn_exceptions.py`, new):** request/response and internal step-boundary shapes; typed domain exceptions.
  - **Config (`app/config.py`, modified):** new named constants — no magic numbers per CLAUDE.md.
  - **Dependency added:** `sse-starlette`, for named SSE events (`narration`, `done`) via `EventSourceResponse`.
  - **Explicitly out of scope:** `routers/turn.py` (stays empty — `pipeline.py`'s entrypoint is what a future spec wires to it), `session/notification_manager.py`/`spectator_manager.py` (multiplayer turn-order *notification push* and spectating), checkpoint advancement, master-mode tool-calling.

- **Sequence Flow (`pipeline.run_turn`):**
  1. Caller (a future router) provides `playthrough_id`, `participant_id`, `action_text`.
  2. `request_receiver.py`: loads `Playthrough` (via `playthrough_repo`) and `Participant`s (via `participant_repo`); validates `Playthrough.status == "active"`, the participant belongs to this playthrough, and — if more than one participant exists — that it is this participant's turn (`turn_order_position` check). Raises `PlaythroughNotActiveError` / `ParticipantNotFoundError` / `TurnOrderError` on failure. Returns a validated `TurnRequest`.
  3. `state_loader.py`: loads the same `Playthrough` row's `scenario_snapshot` and `state.narrative.turns_so_far` — **never reads `Scenario` directly**, per ADR-8. Returns a `LoadedState` (snapshot + state + `turn_count`; `checkpoint` carried through unused).
  4. `ai_orchestrator.py`: builds a prompt from `scenario_snapshot.narrator_persona` + `world_data` + the last `turn_history_window_size` entries of `turns_so_far` + `action_text`; calls `gemini_client.stream_narration(...)`, an async generator. On timeout, retries up to `gemini_max_retries` times with backoff; if exhausted, yields one degradation message and raises `NarrationGenerationError` — the turn is never committed.
  5. `response_streamer.py` and `state_writer.py` run together: `response_streamer.py` wraps the generator in `EventSourceResponse`, emitting `narration` events as chunks arrive (never buffering the full response — CLAUDE.md's SSE rule). Once the generator is exhausted, the accumulated full narration text is handed to `state_writer.py`.
  6. `state_writer.py` persists, in order: (a) `turn_log_repo.create(...)` — new `TurnLog` row; (b) `playthrough_repo.update_state(...)` — appends the turn to `turns_so_far`, increments `turn_count`; (c) if `turn_count == 10`, `scenario_repo.increment_play_count(scenario_id)`. Transient Postgres failures are retried; exhaustion raises `StateWriteError`.
  7. `response_streamer.py` emits `done` only after the write in step 6 succeeds. If the write ultimately fails, it emits a graceful degradation event instead of `done` — the client is told the turn didn't save rather than seeing a false completion.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Test:** `cd apps/turn-resolution-service && pytest tests/turn/ tests/repositories/ -v`
- **Lint / Format:** `cd apps/turn-resolution-service && ruff format . && ruff check . --fix`
- **Full backend suite (regression check):** `cd apps/turn-resolution-service && pytest -v`

### 3.2. Testing Strategy & Conformance
- **Location:** `apps/turn-resolution-service/tests/turn/steps/test_*.py` (one per step, unit-level, mocking repositories and `gemini_client`), `apps/turn-resolution-service/tests/turn/test_pipeline.py` (one integration test), `apps/turn-resolution-service/tests/repositories/test_*.py` (one per new repository).
- **Framework:** `pytest-asyncio`. Per CLAUDE.md: unit tests mock external calls (Gemini, and here also the repositories, since these are unit tests of step logic); the pipeline integration test runs against a real test Postgres instance — **the database is never mocked** — with only `gemini_client` mocked (already a mock module; the test controls its simulated output/failure rate directly).
- **Deterministic test cases:**
  1. **`request_receiver` happy path (solo):** active playthrough, valid participant, single participant → passes, returns `TurnRequest`.
  2. **`request_receiver`: playthrough not active:** `status in {"completed", "abandoned"}` → `PlaythroughNotActiveError`.
  3. **`request_receiver`: unknown participant:** `participant_id` not in playthrough → `ParticipantNotFoundError`.
  4. **`request_receiver`: multiplayer, out-of-turn action:** two participants, acting participant's `turn_order_position` doesn't match whose turn it is → `TurnOrderError`.
  5. **`request_receiver`: multiplayer, correct turn:** matching `turn_order_position` → passes.
  6. **`state_loader`: snapshot fidelity:** loaded `scenario_snapshot`/`turns_so_far` exactly match what's stored on the `Playthrough` row; confirms no `Scenario` table read occurs (assert on a query-count/mock, not just on returned values).
  7. **`ai_orchestrator`: happy path:** mocked `gemini_client` yields chunks → orchestrator returns a generator whose concatenation matches the mocked output.
  8. **`ai_orchestrator`: timeout then success on retry:** mocked client times out once, then succeeds → narration still produced, retry count asserted.
  9. **`ai_orchestrator`: retries exhausted:** mocked client always times out → `NarrationGenerationError` raised, degradation message present in what was yielded before the raise.
  10. **`state_writer`: normal persistence:** `TurnLog` row created, `Playthrough.state.narrative.turns_so_far` appended, `turn_count` incremented by 1, `Scenario.play_count` **unchanged** (turn_count != 10).
  11. **`state_writer`: play_count increment boundary:** `turn_count` transitions to exactly 10 → `Scenario.play_count` incremented by 1; transitions to 9 or 11 → unchanged (off-by-one guard).
  12. **`state_writer`: write failure exhausted:** repository mocked to always fail → `StateWriteError` raised after retry attempts.
  13. **Pipeline integration (real Postgres):** seed a `Playthrough`+`Participant` (reusing the same seeding pattern as `test_playthrough_service.py` in Core API, or an equivalent local fixture), run `pipeline.run_turn(...)` end-to-end with mocked `gemini_client`, assert: SSE stream yields `narration` events followed by `done`, a `TurnLog` row exists in Postgres, `Playthrough.turn_count`/`state` updated, response only completes after the DB write is visible.
  14. **Pipeline integration: write failure degrades gracefully:** `state_writer`'s repository call forced to fail (monkeypatched) → stream emits a degradation event instead of `done`, and the `TurnLog`/`state` are confirmed **not** updated (no partial write visible).

### 3.3. Project Structure & File Layout
- **Files created:**
  - `apps/turn-resolution-service/app/repositories/playthrough_repo.py`
  - `apps/turn-resolution-service/app/repositories/turn_log_repo.py`
  - `apps/turn-resolution-service/app/repositories/participant_repo.py`
  - `apps/turn-resolution-service/app/repositories/scenario_repo.py`
  - `apps/turn-resolution-service/tests/repositories/test_playthrough_repo.py`
  - `apps/turn-resolution-service/tests/repositories/test_turn_log_repo.py`
  - `apps/turn-resolution-service/tests/repositories/test_participant_repo.py`
  - `apps/turn-resolution-service/tests/repositories/test_scenario_repo.py`
  - `apps/turn-resolution-service/tests/turn/steps/test_request_receiver.py`
  - `apps/turn-resolution-service/tests/turn/steps/test_state_loader.py`
  - `apps/turn-resolution-service/tests/turn/steps/test_ai_orchestrator.py`
  - `apps/turn-resolution-service/tests/turn/steps/test_state_writer.py`
  - `apps/turn-resolution-service/tests/turn/steps/test_response_streamer.py`
  - `apps/turn-resolution-service/tests/turn/test_pipeline.py`
  - `docs/specs/turn-resolution-pipeline.spec.md` (this file)
- **Files filled in (previously empty stubs):**
  - `apps/turn-resolution-service/app/turn/pipeline.py`
  - `apps/turn-resolution-service/app/turn/steps/request_receiver.py`
  - `apps/turn-resolution-service/app/turn/steps/state_loader.py`
  - `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py`
  - `apps/turn-resolution-service/app/turn/steps/state_writer.py`
  - `apps/turn-resolution-service/app/turn/steps/response_streamer.py`
  - `apps/turn-resolution-service/app/integrations/gemini_client.py`
  - `apps/turn-resolution-service/app/models/turn.py`
  - `apps/turn-resolution-service/app/exceptions/turn_exceptions.py`
- **Files modified:**
  - `apps/turn-resolution-service/app/config.py` — new settings/constants (§3.4).
  - `apps/turn-resolution-service/requirements.txt` — add `sse-starlette`.
- **Files explicitly NOT touched:** `app/routers/turn.py`, `app/routers/session.py`, `app/session/*`, `app/turn/steps/condition_evaluator.py`, `context_retrieval.py`, `tool_handler.py`, `state_validator.py`, `memory_writer.py`, `app/models/game_state.py`, `app/models/tool_call.py` (all stay empty — genuinely out of scope, not silently deferred), `app/main.py` (no router to register yet).

### 3.4. Code Style & Interfaces

**`app/config.py` additions:**
```python
gemini_timeout_seconds: int = 30
gemini_max_retries: int = 2
turn_history_window_size: int = 10
play_count_increment_turn_threshold: int = 10
```

**`app/models/turn.py`:**
```python
"""Pydantic request/response and internal step-boundary shapes for turn resolution."""

import uuid

from pydantic import BaseModel


class TurnRequestInput(BaseModel):
    """Raw input to the turn pipeline."""

    playthrough_id: uuid.UUID
    participant_id: uuid.UUID
    action_text: str


class TurnRequest(TurnRequestInput):
    """Validated turn request, produced by request_receiver."""

    turn_count: int


class LoadedState(BaseModel):
    """Scenario snapshot + playthrough state, produced by state_loader."""

    scenario_snapshot: dict[str, object]
    state: dict[str, object]
    turn_count: int
    checkpoint: str | None
```

**`app/exceptions/turn_exceptions.py`:**
```python
"""Turn pipeline domain exception classes."""

from app.exceptions.base import BaseAppException


class PlaythroughNotActiveError(BaseAppException):
    """Raised when a turn is submitted against a non-active playthrough."""

    def __init__(self, message: str = "Playthrough is not active"):
        super().__init__(message=message, status_code=409)


class ParticipantNotFoundError(BaseAppException):
    """Raised when the acting participant doesn't belong to the playthrough."""

    def __init__(self, message: str = "Participant not found"):
        super().__init__(message=message, status_code=404)


class TurnOrderError(BaseAppException):
    """Raised when a participant acts out of turn in a multiplayer playthrough."""

    def __init__(self, message: str = "It is not this participant's turn"):
        super().__init__(message=message, status_code=409)


class NarrationGenerationError(BaseAppException):
    """Raised when Gemini narration generation fails after retries."""

    def __init__(self, message: str = "Narration generation failed"):
        super().__init__(message=message, status_code=502)


class StateWriteError(BaseAppException):
    """Raised when persisting turn state fails after retries."""

    def __init__(self, message: str = "Failed to persist turn state"):
        super().__init__(message=message, status_code=500)
```

**`app/repositories/scenario_repo.py` (minimal, by design):**
```python
"""SQL access for the single Scenario field TRS is permitted to touch."""

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario


class ScenarioRepo:
    """TRS may only ever increment play_count on Scenario (CLAUDE.md)."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def increment_play_count(self, scenario_id: uuid.UUID) -> None:
        """Increment play_count by 1. The only Scenario mutation TRS performs."""
        await self._session.execute(
            update(Scenario)
            .where(Scenario.scenario_id == scenario_id)
            .values(play_count=Scenario.play_count + 1)
        )
```
No `get_by_id` or any other method is defined on this repo — the absence of read/write access to any other field is enforced at the repository boundary itself, not just by convention.

**`app/turn/steps/state_writer.py` (core method, illustrating persistence + play_count ordering):**
```python
async def write_turn(
    loaded_state: LoadedState,
    turn_request: TurnRequest,
    narration_text: str,
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
    scenario_id: uuid.UUID,
) -> None:
    """Persist a completed turn: TurnLog row, updated state, conditional play_count."""
    await turn_log_repo.create(
        playthrough_id=turn_request.playthrough_id,
        turn_number=loaded_state.turn_count + 1,
        participant_id=turn_request.participant_id,
        action_text=turn_request.action_text,
        narration_text=narration_text,
    )

    new_turn_count = loaded_state.turn_count + 1
    updated_state = _append_turn(loaded_state.state, turn_request.action_text, narration_text)
    await playthrough_repo.update_state(
        turn_request.playthrough_id, updated_state, new_turn_count
    )

    if new_turn_count == settings.play_count_increment_turn_threshold:
        await scenario_repo.increment_play_count(scenario_id)
```
`_append_turn` is a separate pure function (no I/O) that returns a new `turns_so_far` list — kept out of this function so `write_turn` stays I/O orchestration only, per CLAUDE.md's single-responsibility rule.

**`app/integrations/gemini_client.py` (mock, mirrors `memory_client.py`'s pattern):**
```python
"""MOCK IMPLEMENTATION of the Gemini narration client.

Phase 0-3: returns simulated streamed narration so the turn pipeline can be
built and tested end-to-end without a live Vertex AI dependency. Swappable
for the real client in a later phase with zero changes to any caller —
ai_orchestrator.py only depends on the stream_narration(...) signature below.
"""

from collections.abc import AsyncIterator

MOCK_TIMEOUT_RATE: float = 0.0


async def stream_narration(prompt: str) -> AsyncIterator[str]:
    """Yield simulated narration chunks for the given prompt."""
    ...
```

### 3.5. Git & Review Workflow
- **Branch name:** `feat/trs-turn-pipeline`
- **Commit scope:** repositories layer in one commit, models/exceptions/config in another, the five step implementations + `pipeline.py` in a third, tests can accompany each or land as a final commit — either is fine, but keep this scoped to `apps/turn-resolution-service/` files listed in §3.3 only; don't mix in unrelated changes already in the working tree.
- **PR validation checklist:**
  - [ ] `ruff format --check .` and `ruff check .` clean in `apps/turn-resolution-service/`
  - [ ] All test cases in §3.2 pass, including the real-Postgres integration test
  - [ ] No `Any` types; every function has full type hints; no function over 30 lines
  - [ ] No step in `app/turn/steps/` imports another step — grep to confirm
  - [ ] `ScenarioRepo` exposes only `increment_play_count`
  - [ ] SSE narration streams progressively — confirm via the integration test that events arrive incrementally, not as one buffered payload

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** keep `pipeline.py` as the sole sequencer — steps never import each other; call `gemini_client` only from `ai_orchestrator.py`; call `memory_client` from nowhere in this pipeline (not used at all this pass); emit `done` only after `state_writer` has confirmed the write succeeded.
- ⚠️ **Ask First:** adding `context_retrieval.py`/`condition_evaluator.py`/`memory_writer.py` into the sequence — explicitly deferred; revisit only when the memory-layer retrieval and `ScenarioCondition` work is separately scoped. Adding checkpoint-advancement logic to `state_writer.py` — deferred, no existing precedent for the transition rule.
- 🚫 **Never:** let `state_writer.py` write any `Scenario` field other than `play_count`; let any step read `Scenario` directly instead of `Playthrough.scenario_snapshot` (ADR-8); buffer the full Gemini response before streaming any of it; wire the real Vertex AI SDK into `gemini_client.py` in this task (mock only, per scope).

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Gemini timeout, retries exhausted:** `ai_orchestrator` raises `NarrationGenerationError` after `gemini_max_retries` attempts; no `TurnLog`/state write ever happens (the orchestrator step fails before `state_writer` runs) — the player sees a "taking longer than expected, please try again" style in-stream message but the turn is not consumed (their `action_text` isn't recorded, so they can safely resubmit).
- **Postgres write failure after full narration generated:** the player already saw the narration stream (it was never buffered), but the turn didn't save. `response_streamer` emits a distinct degradation event (not `done`) so the client can tell the difference and reasonably decide whether to retry the write or the whole action — behavior mirrors the RFC's stated policy ("state continues from next successful write") rather than silently dropping the narration the player already read.
- **Multiplayer, simultaneous submissions:** only the participant matching `turn_order_position` passes `request_receiver`; a second, out-of-turn submission is rejected with `TurnOrderError` before any Gemini call is made — this also protects against wasted Gemini spend on rejected turns.
- **`turn_count` exactly at 9 vs 10 vs 11:** `play_count` increments only on the exact transition to 10 (test case 11, §3.2) — not "if turn_count >= 10," to guarantee the increment fires exactly once over a playthrough's lifetime even if this code path could ever be hit more than once (it currently can't, since `turn_count` only increases by 1 per successful write, but the exact-equality check is the more defensible invariant to encode either way).
- **Single-participant playthrough:** turn-order validation is skipped entirely when `len(participants) == 1` — no `turn_order_position` comparison needed or meaningful.
- **`scenario_snapshot.active_conditions` is always `[]` today:** `ai_orchestrator`'s prompt construction does not reference it at all this pass (no `condition_evaluator` step exists yet) — this is a known, intentional gap, not a bug to work around here.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Contracts & Exceptions & Config):** `app/models/turn.py`, `app/exceptions/turn_exceptions.py`, `app/config.py` additions. Verify with `ruff check`.
- [ ] **Task 2 (Repositories):** `playthrough_repo.py`, `turn_log_repo.py`, `participant_repo.py`, `scenario_repo.py`. Pass `pytest tests/repositories/ -v`.
- [ ] **Task 3 (Gemini mock client):** `app/integrations/gemini_client.py`. Verify with `ruff check` (exercised indirectly by Task 4's tests).
- [ ] **Task 4 (Steps):** implement all five step files. Pass `pytest tests/turn/steps/ -v`.
- [ ] **Task 5 (Pipeline):** implement `app/turn/pipeline.py` sequencing the five steps. Pass `pytest tests/turn/test_pipeline.py -v`.
- [ ] **Task 6 (Full Regression):** `pytest -v` (full `apps/turn-resolution-service` suite) and `ruff format --check . && ruff check .` — confirm no regressions in existing `test_connection.py`/`test_memory_client.py`.

## 6. Explicitly Deferred (Not Gaps — Separately Scoped Work)
- `routers/turn.py` — HTTP entrypoint wiring `pipeline.run_turn` to `POST /v1/turn`.
- `context_retrieval.py`, `condition_evaluator.py`, `memory_writer.py` — memory-layer retrieval and `ScenarioCondition`/`active_conditions` evaluation; blocked on `condition_repo.py`/`ScenarioCondition` not existing anywhere in the codebase yet.
- `tool_handler.py`, `state_validator.py`, `app/models/game_state.py`, `app/models/tool_call.py` — master-mode Gemini tool-calling and ADR-4 validate-before-apply; blocked on master-mode `state_schema`-driven state seeding not existing yet (Core API's `playthrough_service.py` is newbie-mode only today).
- `session/notification_manager.py` — multiplayer `your_turn` push notifications; this spec validates turn order but doesn't notify the next participant.
- Checkpoint advancement in `state_writer.py`.
- Real Vertex AI SDK wiring in `gemini_client.py`.
