# Spec: Playthrough Creation (`POST /v1/playthroughs`)

## 1. Objective & User Outcome
- **Problem Statement:** `Playthrough` is currently a schema with no code behind it — `playthrough_repo.py`, `playthrough_service.py`, `routers/playthroughs.py`, `models/playthrough.py`, and `exceptions/playthrough_exceptions.py` are all empty. Nothing writes `scenario_snapshot`/`scenario_version`, nothing triggers the memory-layer clone (ADR-7), and no player can actually start a playthrough. Phase 3 (multiplayer) and Phase 4 (real memory-layer swap) both build directly on `Playthrough` being created correctly — a hasty or partial implementation here is a foundation defect that compounds later, so this must be done correctly and completely now rather than patched incrementally.
- **User Story:** As a player, I want to start a playthrough of a published scenario by submitting my setup answers, and have the game world (structured content snapshot + a private clone of the scenario's world facts) ready before I take my first turn, so that turn resolution never has to conditionally check whether my playthrough's foundation exists.
- **Success Criteria:**
  - `POST /v1/playthroughs` returns `201 Created` only after the scenario snapshot is written **and** the memory-layer clone has succeeded — never before.
  - If the memory clone fails, no `Playthrough` or `Participant` row is ever persisted (fully atomic; no orphaned/partial playthroughs, no compensating rollback logic needed).
  - `Playthrough.scenario_version` and `Playthrough.scenario_snapshot` are populated from the scenario's live state at the moment of creation, and are never re-read from `Scenario` afterward (ADR-8).
  - A user can create multiple concurrent `active` playthroughs of the same scenario; each is independently addressable by its own `playthrough_id`.
  - `GET /v1/playthroughs/{playthrough_id}` returns everything a client needs to render post-creation, gated to participants only.
  - This scope is explicitly newbie-mode only — master-mode `state_schema`-driven state seeding is not built here; the state/snapshot shapes are chosen so master mode can be added later without a redesign.

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **Router (`app/routers/playthroughs.py`, new):** `POST /v1/playthroughs`, `GET /v1/playthroughs/{playthrough_id}`.
  - **Service (`app/services/playthrough_service.py`, new):** orchestrates validation, snapshot construction, initial-state construction, the atomic create-then-clone sequence, and access-gated reads.
  - **Repository (`app/repositories/playthrough_repo.py`, new):** all SQL for `Playthrough` — full CRUD (`create`, `get_by_id`, `update`, `delete`, `list_by_scenario`), per CLAUDE.md's one-repo-per-entity rule.
  - **Repository (`app/repositories/participant_repo.py`, new):** all SQL for `Participant` — full CRUD.
  - **Memory client (`app/integrations/memory_client.py`, existing mock, unmodified):** reuses `clone_template_memory_space(MemoryTemplateCloneRequest) -> MemoryTemplateCloneResponse` — this **is** the `/v1/memory/playthrough/{id}/init` operation described in the RFC, under the client function name already established in this codebase. No new client function or model needed.
  - **Scenario Repo (`app/repositories/scenario_repo.py`, existing):** `get_by_id` to fetch the scenario being played.
  - **Models (`app/models/playthrough.py`, new):** `PlaythroughCreate`, `PlaythroughResponse`.
  - **Exceptions (`app/exceptions/playthrough_exceptions.py`, new):** `ScenarioNotPublishedError`, `InvalidSetupValuesError`, `PlaythroughMemoryCloneError`, `PlaythroughNotFoundError`, `PlaythroughAccessDeniedError`.
  - **ORM (`app/db/models/playthrough.py`, `app/db/models/participant.py`, existing, unmodified):** no migration needed — `scenario_version`/`scenario_snapshot` columns already exist in `001_initial_schema.py`.

- **Sequence Flow (`POST /v1/playthroughs`):**
  1. Client sends `{scenario_id, setup_values}`.
  2. Router → `PlaythroughService.create_playthrough(user_id, data)`.
  3. Service fetches the `Scenario` via `ScenarioRepo.get_by_id`. `404` (`ScenarioNotFoundError`, reused from `scenario_exceptions.py`) if missing/archived.
  4. Service checks `scenario.status == "published"`. If not → `409` `ScenarioNotPublishedError`. (This check is also what transitively guarantees a template memory space exists — `Scenario.status` only ever becomes `"published"` in `publish_service.run_publish_job` *after* `ingest_scenario_template` has already succeeded, so a published scenario is provably clone-able. See `publish_service.py:97-100`.)
  5. Service validates `setup_values` against `scenario.setup_schema` (required fields present; `select`-type fields' values are within `options`). Mismatch → `422` `InvalidSetupValuesError`.
  6. Service constructs the initial `Playthrough.state` dict (namespaced — see §3.4) and the `scenario_snapshot` dict (see §3.4). It explicitly generates `playthrough_id = uuid.uuid4()` itself and passes it into both the `Playthrough` and `Participant` ORM objects. **Correction from the original spec draft:** `Playthrough.playthrough_id`'s `default=uuid.uuid4` column default is a SQLAlchemy INSERT-time default — it is only evaluated at flush, not at Python object construction — so it cannot be relied on to produce the ID before the clone call below. Generating the ID explicitly in the service is what actually gives us an ID before any SQL is sent.
  7. Service calls `memory_client.clone_template_memory_space(MemoryTemplateCloneRequest(scenario_id=..., playthrough_id=<already-generated id>))`.
  8. **If the clone call raises:** service raises `PlaythroughMemoryCloneError` (502). Nothing was ever added to the session — no partial `Playthrough` or `Participant` row exists in Postgres. This is the entire atomicity mechanism; no explicit rollback/compensation code is needed.
  9. **If the clone succeeds:** service adds both ORM objects to the session via `PlaythroughRepo.create` / `ParticipantRepo.create` (flush, not commit — commit happens at the request boundary via `get_db_session`'s existing commit-on-success behavior), and returns `PlaythroughResponse`.
  10. Router returns `201 Created`.

- **Sequence Flow (`GET /v1/playthroughs/{playthrough_id}`):**
  1. Service fetches the playthrough. `404` if missing.
  2. Service checks the requesting user is a `Participant` of this playthrough (owner or joined). Not a participant → `403 PlaythroughAccessDeniedError` (confirmed: existence of a playthrough is not treated as sensitive the way a draft scenario's existence is — a non-participant is told plainly they don't have access, not given a `404`).
  3. Returns `PlaythroughResponse`.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Test:** `cd apps/core-api && pytest tests/services/test_playthrough_service.py tests/routers/test_playthrough_router.py -v`
- **Lint / Format:** `cd apps/core-api && ruff format . && ruff check . --fix`
- **Full backend suite (regression check):** `cd apps/core-api && pytest -v`

### 3.2. Testing Strategy & Conformance
- **Location:** `apps/core-api/tests/services/test_playthrough_service.py` (new), `apps/core-api/tests/routers/test_playthrough_router.py` (new).
- **Framework:** `pytest-asyncio`, against the real test Postgres instance via the existing `db_session`/`async_client` fixtures in `tests/conftest.py`. Only `app.integrations.memory_client.clone_template_memory_space` is mocked (via monkeypatch), per CLAUDE.md's "do not mock the database" rule — the mock module itself (`memory_client.py`) is left exactly as-is; failure is simulated by monkeypatching the function to raise within a specific test, not by modifying the mock's default behavior.
- **Deterministic test cases:**
  1. **Happy path:** published newbie-mode scenario + valid `setup_values` → `201`, `scenario_version` matches `Scenario.current_version` at creation time, `scenario_snapshot` contains `narrator_persona`/`state_schema`/`end_conditions`/`checkpoints`/`active_conditions`/`world_data`, `state` is seeded from setup values, an `owner` `Participant` row exists with `turn_order_position=1`.
  2. **Scenario not published:** `draft`/`publishing`/`archived` scenario → `409`.
  3. **Scenario not found:** unknown/nonexistent `scenario_id` → `404`.
  4. **Missing required setup field:** `setup_schema` has a `required: true` field absent from `setup_values` → `422`.
  5. **Invalid select value:** a `select`-type setup field submitted with a value outside its declared `options` → `422`.
  6. **Memory clone failure:** `clone_template_memory_space` monkeypatched to raise → `502`, and a follow-up DB query confirms **no** `Playthrough` or `Participant` row was created (proves atomicity).
  7. **Multiple concurrent playthroughs:** same user creates two playthroughs of the same published scenario → both succeed, `201` each, distinct `playthrough_id`s, both independently fetchable.
  8. **Multiplayer scenario, solo start:** a scenario with `player_count_support == "multiplayer"` — confirm solo creation is still allowed (multiplayer means "can also be played multiplayer," not "cannot be started solo"; the owner always starts alone and others join later via `POST /v1/playthroughs/join`, which is out of scope here). Assert `201` and a single `owner` participant.
  9. **`GET /v1/playthroughs/{id}` access control:** a non-participant user requesting another user's playthrough is rejected (status per Open Questions below); the owner successfully retrieves it.
  10. **`GET` not found:** unknown `playthrough_id` → `404`.

### 3.3. Project Structure & File Layout
- **Files created:**
  - `apps/core-api/app/repositories/playthrough_repo.py`
  - `apps/core-api/app/repositories/participant_repo.py`
  - `apps/core-api/app/services/playthrough_service.py`
  - `apps/core-api/app/routers/playthroughs.py`
  - `apps/core-api/app/models/playthrough.py`
  - `apps/core-api/app/exceptions/playthrough_exceptions.py`
  - `apps/core-api/tests/services/test_playthrough_service.py`
  - `apps/core-api/tests/routers/test_playthrough_router.py`
  - `docs/specs/playthrough-creation.spec.md` (this file)
- **Files modified:**
  - `apps/core-api/app/main.py` — register `playthroughs.router`.
- **Files explicitly NOT touched:** `app/db/models/playthrough.py`, `app/db/models/participant.py`, `001_initial_schema.py` (no schema changes needed — columns already exist), `app/integrations/memory_client.py` (mock stays as-is per your answer to Q18).

### 3.4. Code Style & Interfaces

**`app/models/playthrough.py`:**
```python
"""Pydantic request and response schemas for Playthroughs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlaythroughCreate(BaseModel):
    """Payload to start a new playthrough of a published scenario."""

    scenario_id: uuid.UUID
    setup_values: dict[str, str] = Field(default_factory=dict)


class PlaythroughResponse(BaseModel):
    """Response model for a created or fetched playthrough."""

    model_config = ConfigDict(from_attributes=True)

    playthrough_id: uuid.UUID
    scenario_id: uuid.UUID
    scenario_title: str
    created_by: uuid.UUID
    state: dict[str, object]
    checkpoint: str | None = None
    turn_count: int
    status: str
    scenario_version: int
    scenario_snapshot: dict[str, object]
    created_at: datetime
    updated_at: datetime
```
`scenario_title` is denormalized onto the response (not stored on `Playthrough` itself — read from the joined `Scenario` at fetch time) purely so a client listing several concurrent playthroughs of possibly-different scenarios can label them without an extra round trip; `playthrough_id` remains the actual identity key.

**`app/exceptions/playthrough_exceptions.py`:**
```python
"""Playthrough domain exception classes."""

from app.exceptions.base import BaseAppException


class PlaythroughNotFoundError(BaseAppException):
    """Raised when a playthrough is not found."""

    def __init__(self, message: str = "Playthrough not found"):
        super().__init__(message=message, status_code=404)


class PlaythroughAccessDeniedError(BaseAppException):
    """Raised when a user is not a participant of the playthrough."""

    def __init__(self, message: str = "Access denied for this playthrough"):
        super().__init__(message=message, status_code=403)


class ScenarioNotPublishedError(BaseAppException):
    """Raised when a playthrough is attempted on a non-published scenario."""

    def __init__(self, message: str = "Scenario is not published"):
        super().__init__(message=message, status_code=409)


class InvalidSetupValuesError(BaseAppException):
    """Raised when setup_values fail validation against setup_schema."""

    def __init__(self, message: str = "Invalid setup values"):
        super().__init__(message=message, status_code=422)


class PlaythroughMemoryCloneError(BaseAppException):
    """Raised when the memory-layer template clone fails at creation time."""

    def __init__(self, message: str = "Failed to initialize playthrough memory"):
        super().__init__(message=message, status_code=502)
```

**`app/services/playthrough_service.py` (core method, illustrating the atomicity mechanism):**
```python
async def create_playthrough(
    self, user_id: uuid.UUID, data: PlaythroughCreate
) -> PlaythroughResponse:
    """Create a playthrough: snapshot the scenario, seed state, clone memory."""
    scenario = await self.scenario_repo.get_by_id(data.scenario_id)
    if not scenario or scenario.status == "archived":
        raise ScenarioNotFoundError()
    if scenario.status != "published":
        raise ScenarioNotPublishedError()

    _validate_setup_values(scenario.setup_schema, data.setup_values)

    # Generated explicitly: the ORM column's `default=uuid.uuid4` only
    # fires at flush/INSERT time, not at object construction, so it can't
    # supply an ID before the clone call below.
    playthrough_id = uuid.uuid4()
    playthrough = Playthrough(
        playthrough_id=playthrough_id,
        scenario_id=scenario.scenario_id,
        created_by=user_id,
        state=_build_initial_state(data.setup_values),
        scenario_version=scenario.current_version,
        scenario_snapshot=_build_snapshot(scenario),
    )
    participant = Participant(
        playthrough_id=playthrough_id,
        user_id=user_id,
        role="owner",
        turn_order_position=1,
    )

    await self._clone_memory_space(scenario.scenario_id, playthrough_id)

    created = await self.playthrough_repo.create(playthrough)
    await self.participant_repo.create(participant)
    return _to_response(created, scenario.title)
```
Note the ordering: both ORM objects exist fully in memory (IDs included, via an explicitly generated `uuid.uuid4()` — not the ORM column default) before the clone call, and `session.add()` never happens until after the clone succeeds — no explicit `try/rollback` around the DB write is needed because nothing was ever staged on the session to roll back.

**Snapshot builder** — single unified builder, no mode branching (master-mode fields are simply empty for a newbie scenario today, ready to populate once master mode is built):
```python
def _build_snapshot(scenario: Scenario) -> dict[str, object]:
    """Freeze the scenario content TRS reads during turns (ADR-8)."""
    return {
        "narrator_persona": scenario.narrator_persona,
        "world_data": scenario.world_data,
        "state_schema": scenario.state_schema,
        "end_conditions": scenario.end_conditions,
        "checkpoints": scenario.checkpoints,
        "active_conditions": [],  # ScenarioCondition rows — out of scope, no condition_repo exists yet
    }
```
`world_data` is included as an intentional, documented deviation from the README's ADR-8 list (which names only `narrator_persona, state_schema, end_conditions, checkpoints, active conditions`) — per your direction, this is because `world_data` (freeform lore / structured world content) needs to be directly visible to the player on the play screen, not just retrievable indirectly through memory-layer queries. `active_conditions` is left as an empty list rather than wired to a real `ScenarioCondition` query, since no `condition_repo.py` exists in this codebase yet and master-mode authoring is out of scope.

**Initial state builder** — namespaced, newbie-mode only:
```python
def _build_initial_state(setup_values: dict[str, str]) -> dict[str, object]:
    """Seed Playthrough.state. Newbie-mode only: opening prompt + setup values."""
    return {
        "setup": dict(setup_values),
        "narrative": {"opening_prompt": None, "turns_so_far": []},
    }
```
The `"setup"` / `"narrative"` (and future `"game"`, for master mode) namespacing keeps player-declared setup data structurally separate from anything TRS or the AI narrator ever mutates, so master mode's future `state_schema`-driven seeding can add a `"game"` key without touching or colliding with what's already here.

### 3.5. Git & Review Workflow
- **Branch name:** `feat/playthrough-creation`
- **Commit scope:** one commit for backend models/exceptions, one for repo/service logic, one for router + `main.py` registration, one for tests — or squash to a single well-described commit; either is fine, but do not mix this with unrelated changes already sitting in the working tree (per `git status`, several other files are already modified — this feature's commits should touch only the files listed in §3.3).
- **PR validation checklist:**
  - [ ] `ruff format --check .` and `ruff check .` clean
  - [ ] All 10 test cases in §3.2 pass against the real test Postgres instance
  - [ ] No `Any` types; every function has full type hints
  - [ ] Router → Service → Repository layering respected (no SQL outside `playthrough_repo.py`/`participant_repo.py`, no `memory_client` calls outside the service)
  - [ ] `playthroughs.router` registered in `main.py`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** run the targeted test suite before reporting completion; keep the memory clone call as the last step before any DB write (atomicity depends on this ordering); log `PlaythroughMemoryCloneError` with full context (`scenario_id`, attempted `playthrough_id`) before it's mapped to a 502.
- ⚠️ **Ask First:** adding any new column to `Playthrough` (e.g. a future `memory_space_id`) — explicitly deferred per your answer to Q14, revisit only if a concrete downstream need appears.
- 🚫 **Never:** call `memory_client` from the router or repository layer; add a `condition_repo.py`/`ScenarioCondition` read in this task (out of scope — `active_conditions` stays `[]`); build `POST /v1/playthroughs/{id}/share` or `POST /v1/playthroughs/join` in this task (explicitly out of scope per your answer to Q23); commit a `Playthrough`/`Participant` row before the memory clone has confirmed success.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Memory clone failure:** the entire request fails with `502` and zero DB side effects (§3.2 test 6). This is a stricter posture than TRS's own graceful-degradation policy for *runtime* memory batch failures (README "Memory batch failure") — deliberately so, since without an initialized memory space the playthrough cannot function at all (per your answer to Q17: "without it the user can't play"), whereas a mid-game batch failure only degrades retrieval quality.
- **Concurrent creation of two playthroughs by the same user for the same scenario:** both succeed independently; there is no uniqueness constraint on `(scenario_id, created_by)` — confirmed acceptable per your answer to Q4.
- **Scenario edited mid-creation (race):** if a `PATCH /v1/scenarios/{id}` commits between this service's `get_by_id` read and its snapshot construction, the snapshot reflects whichever version was read — no additional locking is introduced for this task; this mirrors the granularity already accepted by ADR-8 (each playthrough locks to *a* version, not necessarily an externally-visible one).
- **`setup_schema` is empty (creator defined no custom fields):** `setup_values` may be `{}`; `_build_initial_state` still produces a valid namespaced state with an empty `"setup"` dict.
- **Idempotency:** `POST /v1/playthroughs` is not idempotent by design — resubmitting creates a new playthrough (consistent with "multiple concurrent playthroughs allowed"). No idempotency key is introduced.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Contracts & Exceptions):** Define `PlaythroughCreate`/`PlaythroughResponse` in `app/models/playthrough.py` and all five exception classes in `app/exceptions/playthrough_exceptions.py`. Verify with `ruff check app/models/playthrough.py app/exceptions/playthrough_exceptions.py`.
- [ ] **Task 2 (Repositories):** Implement `PlaythroughRepo` and `ParticipantRepo` full CRUD in `app/repositories/`. Verify with `ruff check` (no test yet — pure data access, exercised indirectly by Task 3's tests).
- [ ] **Task 3 (Service & Unit-Level Logic):** Implement `PlaythroughService.create_playthrough`, `get_playthrough`, `_build_snapshot`, `_build_initial_state`, `_validate_setup_values` in `app/services/playthrough_service.py`. Pass `pytest tests/services/test_playthrough_service.py -v`.
- [ ] **Task 4 (Router & Wiring):** Implement `POST /v1/playthroughs` and `GET /v1/playthroughs/{playthrough_id}` in `app/routers/playthroughs.py`; register in `main.py`. Pass `pytest tests/routers/test_playthrough_router.py -v`.
- [ ] **Task 5 (Full Regression):** Run `pytest -v` (full suite) and `ruff format --check . && ruff check .` to confirm no regressions in existing scenario/publish tests.

---

## Decisions Confirmed (no longer open)
1. **`GET /v1/playthroughs/{id}` non-participant response is `403`** — a non-participant is told plainly they lack access; playthrough existence is not treated as sensitive.
2. **`setup_values` typed as `dict[str, str]`** — confirmed sufficient for `setup_schema`'s current `text`/`select` field types.
