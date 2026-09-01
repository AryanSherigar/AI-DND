# Spec: Scenario Domain CRUD Service & API Endpoints

## 1. Objective & User Outcome
- **Problem Statement:** Creators need a reliable, secure backend API to create, view, edit, list, and soft/hard-delete scenario definitions (both Newbie and Master modes) without exposing private draft scenarios to non-creators or corrupting active playthroughs when updating/deleting scenario rules.
- **User Story:** As a creator on AI-DND, I want to manage my scenarios (create, retrieve, update metadata/story schemas, list my drafts, delete unused scenarios) via a clean REST API so that I can author immersive worlds and make them available for discovery and gameplay.
- **Success Criteria:**
  - `POST /v1/scenarios` creates draft scenarios with proper validation (requiring `title`, `mode`, `complexity_tier`) and default fallback values.
  - `GET /v1/scenarios/{id}` enforces access control for draft scenarios (returning `404 Not Found` for unauthorized users) and public access for published scenarios.
  - `PATCH /v1/scenarios/{id}` enforces mode immutability, allows creator-only updates, and selectively increments `current_version` (+1) ONLY when story/gameplay fields are modified.
  - `DELETE /v1/scenarios/{id}` performs a hard delete if zero playthroughs exist, or soft-deletes (`status = 'archived'`) if active/past playthroughs reference it, maintaining in-flight game integrity.
  - `GET /v1/scenarios` supports discovery filtering (`genre_tags`, `complexity_tier`, `player_count_support`, `sort`, `cursor`) and creator dashboard listing (`mine=true`).
  - Zero warnings under `ruff format` and `ruff check`, 100% adherence to repository architecture boundaries (Router → Service → Repository → DB).

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **FastAPI Router (`app/routers/scenarios.py`):** Handles HTTP endpoints, query/body parsing, auth dependency (`get_current_user`), and maps domain exceptions.
  - **Scenario Service (`app/services/scenario_service.py`):** Implements business logic, access control checks, selective version increment logic, and deletion strategy decision (hard delete vs. soft archive).
  - **Scenario Repository (`app/repositories/scenario_repo.py`):** Pure SQLAlchemy async database access layer. Handles SQL queries, filtering, sorting, insertion, and mutation.
  - **Pydantic Schemas (`app/models/scenario.py`):** Strict request/response DTO contracts for create, update, detail, summary, and paginated list output.
  - **Domain Exceptions (`app/exceptions/scenario_exceptions.py`):** Standardized app exceptions mapped by `middleware/error_handler.py`.

- **Sequence Flow:**
  1. Client sends HTTP request with bearer auth token.
  2. Middleware `get_current_user` validates token and returns `User` model.
  3. `scenarios.py` router validates request schema (Pydantic) and delegates to `ScenarioService`.
  4. `ScenarioService` executes business logic (e.g. checks `creator_id`, determines version increment on PATCH, checks playthrough count for DELETE).
  5. `ScenarioRepo` executes async SQLAlchemy ORM queries against Postgres.
  6. Service transforms ORM entity to Pydantic Response schema and returns to Router.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Build / Dependencies check:** `pip list` / `python3 -c "import fastapi, pydantic, sqlalchemy"`
- **Test:** `pytest tests/services/test_scenario_service.py tests/routers/test_scenario_router.py -v` (Run from `apps/core-api`)
- **Lint / Format / Type-Check:** `ruff format . && ruff check . --fix` (Run from `apps/core-api`)

### 3.2. Testing Strategy & Conformance
- **Location:** `apps/core-api/tests/services/` and `apps/core-api/tests/routers/`
- **Coverage Requirements:**
  - Happy path for `POST`, `GET`, `PATCH`, `DELETE`, and `GET` list.
  - Unauthorized access attempt on draft scenario returns `404 Not Found`.
  - Non-creator update/delete attempt returns `404 Not Found` (for drafts) or `403 Forbidden` (for published).
  - Immutability check: Attempt to mutate `mode` via `PATCH` raises validation error or is ignored.
  - Version increment check: Updating `title` keeps `current_version` equal; updating `narrator_persona` increments `current_version` by 1.
  - Deletion strategy test: Scenario with 0 playthroughs is deleted from DB; scenario with >0 playthroughs has `status` updated to `'archived'`.

### 3.3. Project Structure & File Layout
- **Files to create:**
  - `apps/core-api/app/exceptions/scenario_exceptions.py`
  - `apps/core-api/app/models/scenario.py`
  - `apps/core-api/app/repositories/scenario_repo.py`
  - `apps/core-api/app/services/scenario_service.py`
  - `apps/core-api/app/routers/scenarios.py`
  - `apps/core-api/tests/services/test_scenario_service.py`
  - `apps/core-api/tests/routers/test_scenario_router.py`
- **Files to modify:**
  - `apps/core-api/app/main.py` (Register `scenarios.router`)

### 3.4. Code Style & Interfaces

#### Pydantic Schemas (`app/models/scenario.py`):
```python
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class ScenarioCreate(BaseModel):
    title: str = Field(..., max_length=255)
    mode: str = Field(..., pattern="^(newbie|master)$")
    complexity_tier: str = Field(..., pattern="^(newbie|intermediate|master)$")
    logline: str | None = Field(default=None, max_length=150)
    player_count_support: str = Field(default="solo", pattern="^(solo|multiplayer|both)$")
    estimated_playtime: str | None = Field(default=None, max_length=50)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    content_tag: str | None = Field(default=None, max_length=100)
    genre_tags: list[str] = Field(default_factory=list)
    narrator_persona: str | None = None
    world_data: dict[str, object] = Field(default_factory=dict)
    setup_schema: list[object] = Field(default_factory=list)
    state_schema: dict[str, object] = Field(default_factory=dict)
    end_conditions: list[object] = Field(default_factory=list)
    checkpoints: list[object] = Field(default_factory=list)
    rules: dict[str, object] = Field(default_factory=dict)

class ScenarioUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    logline: str | None = Field(default=None, max_length=150)
    complexity_tier: str | None = Field(default=None, pattern="^(newbie|intermediate|master)$")
    player_count_support: str | None = Field(default=None, pattern="^(solo|multiplayer|both)$")
    estimated_playtime: str | None = Field(default=None, max_length=50)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    content_tag: str | None = Field(default=None, max_length=100)
    genre_tags: list[str] | None = None
    narrator_persona: str | None = None
    world_data: dict[str, object] | None = None
    setup_schema: list[object] | None = None
    state_schema: dict[str, object] | None = None
    end_conditions: list[object] | None = None
    checkpoints: list[object] | None = None
    rules: dict[str, object] | None = None

class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: uuid.UUID
    creator_id: uuid.UUID
    title: str
    logline: str | None
    mode: str
    status: str
    genre_tags: list[str]
    complexity_tier: str
    player_count_support: str
    estimated_playtime: str | None
    cover_image_url: str | None
    content_tag: str | None
    play_count: int
    rating_avg: Decimal
    narrator_persona: str | None
    world_data: dict[str, object]
    setup_schema: list[object]
    state_schema: dict[str, object]
    end_conditions: list[object]
    checkpoints: list[object]
    rules: dict[str, object]
    current_version: int
    created_at: datetime
    updated_at: datetime
```

#### Domain Exceptions (`app/exceptions/scenario_exceptions.py`):
```python
from app.exceptions.base import BaseAppException

class ScenarioNotFoundError(BaseAppException):
    def __init__(self, message: str = "Scenario not found"):
        super().__init__(message=message, status_code=404)

class ScenarioAccessDeniedError(BaseAppException):
    def __init__(self, message: str = "Access denied for this scenario"):
        super().__init__(message=message, status_code=403)

class ScenarioValidationError(BaseAppException):
    def __init__(self, message: str = "Invalid scenario configuration"):
        super().__init__(message=message, status_code=400)
```

### 3.5. Git & Review Workflow
- **Branch:** `feat/core-api-scenario-crud`
- **PR Scope:** Implementation of domain models, repo, service, router, and integration tests for Scenario CRUD.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:**
  - Follow strict Layering: Router → Service → Repository → DB.
  - Enforce type hints on all functions and return types.
  - Format with `ruff format .` and pass `ruff check . --fix`.
  - Max function length under 30 lines; max nesting depth 2 levels.
- ⚠️ **Ask First:**
  - Modifying DB schema / Alembic migrations.
  - Changing authentication token extraction.
- 🚫 **Never:**
  - Write SQL inside Routers or Services.
  - Return untyped `dict` responses from FastAPI routes.
  - Allow draft scenarios to be exposed to non-creators.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Draft Scenario Probe Defense:** Returning HTTP `404 Not Found` (instead of 403) when non-creators query a draft scenario ID prevents attacker probes from discovering private scenario UUIDs.
- **Concurrent Playthrough Safety:** `PATCH` operations update `Scenario` and bump `current_version`, but in-flight playthroughs remain isolated due to `scenario_snapshot` on `Playthrough`.
- **Foreign Key Protection on Delete:** Attempting to delete a scenario with active playthroughs shifts `status` to `'archived'` instead of throwing a DB `IntegrityError`, preserving game stability.

## 5. Phased Implementation Tasks

- [ ] **Task 1 (Exceptions & Schemas):** Define `app/exceptions/scenario_exceptions.py` and Pydantic DTOs in `app/models/scenario.py`.
- [ ] **Task 2 (Repository Layer):** Implement `app/repositories/scenario_repo.py` with SQLAlchemy async methods (`create`, `get_by_id`, `update`, `delete`, `count_playthroughs`, `list_scenarios`).
- [ ] **Task 3 (Service Layer):** Implement `app/services/scenario_service.py` with business logic (access rules, version increment checks, soft/hard deletion logic).
- [ ] **Task 4 (Router & Registration):** Implement `app/routers/scenarios.py` endpoints (`POST /v1/scenarios`, `GET /v1/scenarios/{id}`, `PATCH /v1/scenarios/{id}`, `DELETE /v1/scenarios/{id}`, `GET /v1/scenarios`) and register in `main.py`.
- [ ] **Task 5 (Tests & Verification):** Implement unit/integration tests in `tests/services/test_scenario_service.py` and `tests/routers/test_scenario_router.py`, run `ruff format` & `ruff check`.
