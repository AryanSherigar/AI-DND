# Spec: Async Scenario Publish Flow

## 1. Objective & User Outcome
- **Problem Statement:** Publishing a scenario previously didn't exist as a real backend flow — the frontend faked it by creating the scenario directly with `status: "published"` in one synchronous `POST /v1/scenarios` call, with no content-tag check and no authoring-time memory ingestion ever triggered. This left the discovery feed, the memory layer template space (ADR-7 in the main RFC), and the creator's publish UX all disconnected from reality.
- **User Story:** As a creator, I want to publish my scenario and see it move through a real "publishing → published" state, with a clear error if the content-tag check or memory ingestion fails, so that a scenario is never live in discovery without having actually passed those checks.
- **Success Criteria:**
  - `POST /v1/scenarios/{id}/publish` returns `202 Accepted` immediately (does not block on content-tag check or ingestion).
  - The scenario is pollable via the existing `GET /v1/scenarios/{id}` and settles into `published` or reverts with a `publish_error` message.
  - A scenario that has ever been published stays visible in `GET /v1/scenarios` (discovery) through a re-publish attempt, even if that re-publish attempt fails.
  - `PATCH /v1/scenarios/{id}` is rejected with `409` while a publish is in flight.
  - Frontend `Step4Review.tsx` no longer fakes publish via `status: "published"` on create; it creates as `draft` and drives the real endpoint via a polling hook.

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **Router (`app/routers/scenarios.py`):** new `POST /{scenario_id}/publish` (202), and a guard added to the existing `PATCH`.
  - **Publish Service (`app/services/publish_service.py`):** two-phase orchestration — `start_publish` (sync, request-scoped) and `run_publish_job` (background, own DB session).
  - **DB session factory (`app/db/connection.py`):** `get_session_factory`, an overridable dependency giving background work its own `AsyncSession`.
  - **Memory client (`app/integrations/memory_client.py`, mocked):** `ingest_scenario_template` — the authoring-time ingestion call (LLM extraction for newbie mode, per the main RFC's Scenario Ingestion section).
  - **Scenario Repo/ORM (`app/repositories/scenario_repo.py`, `app/db/models/scenario.py`):** `published_at`, `publish_error` columns; discovery filter keyed on `published_at`.
  - **Frontend (`usePublish.ts`, `PublishFlow.tsx`, `ContentTagPicker.tsx`, `Step4Review.tsx`, `scenarios.api.ts`):** publish trigger + React Query polling.

- **Sequence Flow:**
  1. Client `POST /v1/scenarios/{id}/publish`.
  2. Router → `PublishService.start_publish`: ownership check, `409` if already `publishing`, flips `status='publishing'`, clears `publish_error`. Returns within the request.
  3. Router schedules `PublishService.run_publish_job` via `BackgroundTasks` (see ADR-10 for why `BackgroundTasks` and not a task queue) and returns `202` with the scenario (now `publishing`).
  4. Background job opens its own session, re-fetches the scenario, runs `_check_content_tag`, then calls `memory_client.ingest_scenario_template`.
  5. On success: `status='published'`, `published_at` set (once, if unset), `publish_error=None`. On failure: `status='draft'` (first-ever publish) or `status='publish_failed'` (re-publish of an already-live scenario, so it doesn't drop out of discovery), `publish_error=str(exc)`.
  6. Client polls `GET /v1/scenarios/{id}` until `status` is no longer `publishing`.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Test (backend):** `cd apps/core-api && pytest tests/services/test_publish_service.py tests/routers/test_scenario_router.py tests/db/test_initial_schema_migration.py -v`
- **Lint / Format:** `cd apps/core-api && ruff check . && ruff format --check .`
- **Frontend dev server:** `cd apps/frontend && npm run dev` (manual verification — no automated frontend test suite exists for studio components)

### 3.2. Testing Strategy & Conformance
- **Location:** `apps/core-api/tests/services/test_publish_service.py` (new), `apps/core-api/tests/routers/test_scenario_router.py` (extended), `apps/core-api/tests/db/test_initial_schema_migration.py` (extended).
- **Real user behavior, not a direct-await shortcut:** router tests hit the actual `202` endpoint and poll `GET` in a bounded retry loop, exercising the real `BackgroundTasks` execution against the test database (via a `get_session_factory` override in `tests/conftest.py` that reuses the test's own session/transaction rather than opening a separate connection that couldn't see uncommitted test data).
- **Coverage:**
  - Happy path: publish → `published`, `published_at` set, visible in discovery.
  - Content-check failure on first-ever publish → reverts to `draft`, `publish_error` set, absent from discovery.
  - Content-check failure on re-publish of a live scenario → `publish_failed`, `published_at` still set, **still visible** in discovery (the specific gap this design closes — see ADR note in the spec's own review).
  - `409` on double-publish (`start_publish` called while already `publishing`).
  - `409` on `PATCH` while `publishing`.

### 3.3. Project Structure & File Layout
- **Files created:**
  - `apps/core-api/tests/services/test_publish_service.py`
  - `docs/adr/010-publish-uses-fastapi-background-tasks.md`
  - `docs/specs/scenario-publish-flow.spec.md` (this file)
- **Files modified:**
  - `apps/core-api/app/services/publish_service.py` (was an empty placeholder)
  - `apps/core-api/app/routers/scenarios.py`
  - `apps/core-api/app/services/scenario_service.py`
  - `apps/core-api/app/repositories/scenario_repo.py`
  - `apps/core-api/app/models/scenario.py`
  - `apps/core-api/app/db/models/scenario.py`
  - `apps/core-api/app/db/connection.py`
  - `apps/core-api/app/db/migrations/versions/001_initial_schema.py` (edited in place — no real deployment exists yet)
  - `apps/core-api/app/exceptions/scenario_exceptions.py`
  - `apps/core-api/tests/conftest.py`
  - `apps/core-api/tests/routers/test_scenario_router.py`
  - `apps/core-api/tests/db/test_initial_schema_migration.py`
  - `apps/frontend/src/features/studio/api/scenarios.api.ts`
  - `apps/frontend/src/features/studio/hooks/usePublish.ts` (was empty)
  - `apps/frontend/src/features/studio/components/PublishFlow/PublishFlow.tsx` (was empty)
  - `apps/frontend/src/features/studio/components/PublishFlow/ContentTagPicker.tsx` (was empty)
  - `apps/frontend/src/features/studio/components/NewbieWizard/Step4Review.tsx`

### 3.4. Code Style & Interfaces

#### `Scenario.status` state machine
```
draft ──(POST /publish)──▶ publishing ──(success)──▶ published
  ▲                              │
  └──────(failure, first publish)┘

published ──(POST /publish)──▶ publishing ──(success)──▶ published
                                     │
                                     └──(failure, re-publish)──▶ publish_failed ──(POST /publish)──▶ publishing ...
```
`published_at` is set once on first success and never cleared by a later failure — it is the discovery-visibility signal, independent of the transient `status` value.

#### `PublishService` (`app/services/publish_service.py`)
```python
ALLOWED_CONTENT_TAGS: set[str] = {"all-ages", "teen", "mature"}

class PublishService:
    def __init__(self, scenario_repo: ScenarioRepo) -> None: ...
    async def start_publish(self, scenario_id: uuid.UUID, user_id: uuid.UUID) -> Scenario: ...

    @staticmethod
    async def run_publish_job(
        scenario_id: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None: ...
```

### 3.5. Git & Review Workflow
- **Branch:** `feat/scenario-publish-flow`
- **PR Scope:** backend publish endpoint + state machine + discovery-filter fix, plus frontend wiring to replace the fake synchronous publish.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** background DB work uses its own session (never the request-scoped one); discovery visibility checks `published_at`, never the transient `status`.
- ⚠️ **Ask First:** changing the content-tag taxonomy (`ALLOWED_CONTENT_TAGS` is a placeholder — no taxonomy existed anywhere in the codebase before this); moving execution off `BackgroundTasks` onto a real queue (see ADR-10).
- 🚫 **Never:** let a failed re-publish clear `published_at` on an already-live scenario; let `PATCH` proceed while `status == 'publishing'`.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **`start_publish` commits explicitly, on purpose:** `BackgroundTasks` in this FastAPI version run *before* `get_db_session`'s post-yield commit, not after — leaving the 'publishing' UPDATE uncommitted would deadlock against `run_publish_job`'s own UPDATE on the same row (confirmed via reproduction; see `docs/adr/010-publish-uses-fastapi-background-tasks.md`). `start_publish` therefore commits its own session before returning.
- **Process restart mid-publish:** out of scope for this pass — a scenario can get stuck in `publishing` if the Core API instance recycles mid-job. See ADR-10 for the required post-hackathon fix (real task queue + reconciliation sweep).
- **No auto-retry:** content-check or ingestion failures surface immediately via `publish_error`; the creator retries by calling `POST /publish` again.
- **Re-publish of a live scenario:** always re-runs both steps; a failure here must not un-publish the scenario (handled via the `published_at`-keyed discovery filter, not the transient `status`).
- **Master mode:** flows through the same endpoint/state machine as newbie mode; the mocked `ingest_scenario_template` already accepts `mode` + `world_data` uniformly, so no branching was needed for this pass. Real master-mode ingestion (direct Entity/Fact writes rather than `world_data`) is future work.

## 5. Phased Implementation Tasks
- [x] **Task 1 (Schema & Migration):** `publish_error`, `published_at` columns; extended `status` CHECK constraint (`001_initial_schema.py`, `db/models/scenario.py`).
- [x] **Task 2 (Service Layer):** `PublishService.start_publish` + `run_publish_job`, content-tag check, `get_session_factory` seam.
- [x] **Task 3 (Router & Discovery):** `POST /{id}/publish`, `PATCH` guard, `published_at`-keyed discovery filter.
- [x] **Task 4 (Tests):** service + router + migration test coverage, real-user-behavior polling via `BackgroundTasks`.
- [x] **Task 5 (Frontend):** `usePublish.ts`, `PublishFlow.tsx`, `ContentTagPicker.tsx`, `Step4Review.tsx` wired to the real endpoint. Verified via `tsc --noEmit`, `ruff`-equivalent (Vite transform of each changed module returns 200 with no compile errors), and manual `curl` exercise of the same backend flow the UI calls — **not** visually verified in an actual browser (no browser-automation tool available in this environment); the dev servers were left running for the user to click through.
- [x] **Task 6 (Docs):** this spec + `docs/adr/010-publish-uses-fastapi-background-tasks.md`.
