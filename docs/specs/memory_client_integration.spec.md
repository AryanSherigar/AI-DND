# Spec: Memory Layer Client Integration & Pydantic Models

## 1. Objective & User Outcome
- **Problem Statement:** The Turn Resolution Service and Core API need a mock client layer for the external graph memory service (`mem1`). Per ADR-9 and recent contract updates, `POST /v1/memory/query` must include a `game_state` snapshot for evaluating `when_active` expressions on pre-authored facts. Core API additionally needs mock endpoints for authoring-time template ingestion and playthrough memory space cloning (ADR-7).
- **User Story:** 
  - As a Turn Resolution Service developer, I want a typed mock `memory_client.py` honoring the updated `MemoryQueryRequest` (carrying `game_state`), `MemoryIngestRequest`, and batch management methods so turn resolution pipelines can simulate retrieval and batched ingestion.
  - As a Core API developer, I want a typed mock `memory_client.py` supporting `ingest_scenario_template` and `clone_template_memory_space` so scenario publishing and playthrough setup flows can simulate memory template initialization and cloning.
- **Success Criteria:**
  - `app/models/memory.py` created in both `apps/turn-resolution-service` and `apps/core-api` with canonical Pydantic v2 schemas (`MemoryQueryRequest` with default `game_state: dict[str, Any]`, `Fact`, `MemoryQueryResponse`, `TurnBatchEntry`, `MemoryIngestRequest`, `MemoryIngestResponse`, `BatchStatus`, `MemoryTemplateIngestRequest`, `MemoryTemplateIngestResponse`, `MemoryTemplateCloneRequest`, `MemoryTemplateCloneResponse`).
  - `apps/turn-resolution-service/app/integrations/memory_client.py` implemented with `query_memory`, `ingest_batch`, `get_batch_status`, and `retry_batch`.
  - `apps/core-api/app/integrations/memory_client.py` implemented with `query_memory`, `ingest_batch`, `get_batch_status`, `retry_batch`, `ingest_scenario_template`, and `clone_template_memory_space`.
  - Full compliance with `AGENTS.md` (type hints on all functions, max nesting ≤ 2, functions < 30 lines, `ruff format` and `ruff check --fix`).
  - Integration tests in both services (`apps/turn-resolution-service/tests/integrations/test_memory_client.py` and `apps/core-api/tests/integrations/test_memory_client.py`) verifying serialization, default `game_state`, failure simulation, and template operations.

## 2. Technical Architecture & Data Flow
- **Components Involved:** FastAPI, Pydantic v2, `apps/turn-resolution-service/app/integrations/memory_client.py`, `apps/core-api/app/integrations/memory_client.py`, test suites in `tests/integrations/`.
- **Sequence Flow:**
  - **Turn Resolution Service (Runtime Query & Ingest):**
    1. Pipeline step `context_retrieval.py` constructs `MemoryQueryRequest` passing current `game_state` snapshot.
    2. `memory_client.query_memory(request)` returns `MemoryQueryResponse` (fake facts or abstention based on `MOCK_ABSTAIN_RATE`).
    3. Pipeline step `memory_writer.py` constructs `MemoryIngestRequest` with turns batch.
    4. `memory_client.ingest_batch(request)` returns `MemoryIngestResponse` with a `batch_id` and records batch status in `_MOCK_BATCH_STATUSES`.
  - **Core API (Authoring Ingest & Template Clone):**
    1. `publish_service.py` calls `memory_client.ingest_scenario_template(request)` when publishing a scenario. Returns `MemoryTemplateIngestResponse` with a `template_space_id`.
    2. `playthrough_service.py` calls `memory_client.clone_template_memory_space(request)` when creating a playthrough. Returns `MemoryTemplateCloneResponse` with a `playthrough_space_id`.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Test TRS Memory Client:** `pytest apps/turn-resolution-service/tests/integrations/test_memory_client.py`
- **Test Core API Memory Client:** `pytest apps/core-api/tests/integrations/test_memory_client.py`
- **Lint / Type-Check:** `ruff check . --fix` and `ruff format .`

### 3.2. Testing Strategy & Conformance
- **Test Files:**
  - `apps/turn-resolution-service/tests/integrations/test_memory_client.py`
  - `apps/core-api/tests/integrations/test_memory_client.py`
- **Test Cases:**
  - `MemoryQueryRequest` accepts and defaults `game_state` properly.
  - `query_memory` returns `MemoryQueryResponse` containing fake facts matching request subject/object and abstention logic when rate toggle set.
  - `ingest_batch` generates unique `batch_id`, sets status in `_MOCK_BATCH_STATUSES`, and simulates failures when rate toggle set.
  - `get_batch_status` and `retry_batch` inspect and transition status correctly from `failed` to `succeeded`.
  - `ingest_scenario_template` and `clone_template_memory_space` return expected response schemas with valid UUIDs.

### 3.3. Project Structure & File Layout
- Files to create:
  - `apps/turn-resolution-service/app/models/memory.py`
  - `apps/turn-resolution-service/app/integrations/memory_client.py`
  - `apps/turn-resolution-service/tests/integrations/test_memory_client.py`
  - `apps/core-api/app/models/memory.py`
  - `apps/core-api/app/integrations/memory_client.py`
  - `apps/core-api/tests/integrations/test_memory_client.py`

### 3.4. Code Style & Interfaces
- Strictly follows Python 3.10+ union types (`T | None`), explicit return hints, Pydantic v2 models, max function length < 30 lines, nesting depth ≤ 2.

### 3.5. Git & Review Workflow
- Branch: `feat/memory-client-integration`
- PR Checklist:
  - Zero `ruff check` or `ruff format` warnings.
  - Integration tests in both services pass via pytest.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Return explicit domain models; log mock state transitions; annotate type hints completely.
- ⚠️ **Ask First:** Changing contract field names or response shapes.
- 🚫 **Never:** Use untyped dicts crossing boundaries; use `Any` except in generic `game_state: dict[str, Any]`; block the event loop.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Abstention Simulation:** `MOCK_ABSTAIN_RATE` toggle forces abstention responses (`abstained=True`, `facts=[]`).
- **Ingest Batch Failure & Retry:** `MOCK_BATCH_FAILURE_RATE` toggle marks batches as `failed` with `retryable=True`. `retry_batch()` updates batch status to `succeeded`.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (TRS Models):** Implement `apps/turn-resolution-service/app/models/memory.py`.
- [ ] **Task 2 (Core API Models):** Implement `apps/core-api/app/models/memory.py`.
- [ ] **Task 3 (TRS Memory Client):** Implement `apps/turn-resolution-service/app/integrations/memory_client.py`.
- [ ] **Task 4 (Core API Memory Client):** Implement `apps/core-api/app/integrations/memory_client.py`.
- [ ] **Task 5 (TRS Tests):** Create and run `apps/turn-resolution-service/tests/integrations/test_memory_client.py`.
- [ ] **Task 6 (Core API Tests):** Create and run `apps/core-api/tests/integrations/test_memory_client.py`.
- [ ] **Task 7 (Lint & Validation):** Execute `ruff format` and `ruff check --fix` across both apps.
