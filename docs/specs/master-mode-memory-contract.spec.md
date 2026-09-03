# Spec: Master-Mode Memory Layer Contract — Direct-Write Ingestion & `when_active`

## 1. Objective & User Outcome

- **Problem Statement:** `PublishService.run_publish_job` already calls `memory_client.ingest_scenario_template(...)` at publish time, but it always sends `world_data` — the newbie-mode freeform-lore shape. Master mode has no `world_data` blob to send (its structured content lives in the `entities`/`facts` tables from `master-mode-data-model.spec.md`), so a master-mode scenario publishes today with nothing meaningful reaching the memory layer. This spec wires the "direct write, no LLM extraction" path the README calls for, and formalizes the `game_state`/`revealed_facts` convention TRS already depends on.
- **User Story:** As a creator who hand-authored every entity and fact precisely, I want publishing my scenario to write exactly what I specified into the memory layer — no LLM reinterpreting my facts — so the trust guarantee master mode promises actually holds at the one point (publish) where ingestion happens.
- **Success Criteria:**
  - Publishing a `master` scenario sends its entities and facts (direct write) to `ingest_scenario_template`; publishing a `newbie` scenario is unchanged (still sends `world_data` for LLM extraction).
  - A fact's `hidden` flag survives the ingest round-trip into the memory layer's stored shape, so a real (future, non-mock) implementation has what it needs to filter on `when_active`/visibility — this spec does not ask the mock to actually perform that filtering (locked decision: mock stays a mock).
  - `POST /v1/memory/query`'s `game_state` field is documented, by convention, to include a `revealed_facts: list[str]` entry (fact IDs whose `hidden` flag is overridden to visible for this specific playthrough) alongside the raw state tree — this is additive to the existing ADR-9 `game_state` contract, not a breaking change, since `game_state` is already `dict[str, Any]`.
  - Playthrough-scoped memory cloning (`ingest_scenario_template` → `clone_template_to_playthrough`, ADR-7) is unaffected by this spec — it already works identically for both modes and needs no master-mode-specific change.
  - Zero `ruff` warnings; no SQL added to `memory_client.py` (it never touches Postgres directly, matching CLAUDE.md's integration boundary — entities/facts are read via the repos from `master-mode-data-model.spec.md`, in `publish_service.py`, then handed to the client as a request object).

## 2. Technical Architecture & Data Flow

- **Components Involved:** `apps/core-api/app/services/publish_service.py`, `apps/core-api/app/integrations/memory_client.py` (mock), `apps/core-api/app/models/memory.py`, `apps/core-api/app/repositories/entity_repo.py` + `fact_repo.py` (from `master-mode-data-model.spec.md`). No Turn Resolution Service files change in this spec — TRS's `game_state`/`revealed_facts` forwarding was already implemented in `master-mode-turn-pipeline.spec.md`'s Task 6 (hidden fact filtering); this spec only documents that convention formally so it's a stable contract, not an implicit one two specs happen to agree on.
- **Reference data:** "The Hollow Cairn" (`docs/specs/master-mode-demo-scenario.md`) — 7 entities, 7 facts (1 hidden), used as the publish-time ingestion fixture.
- **Sequence Flow — publishing a master-mode scenario:**
  1. Creator calls `POST /v1/scenarios/{id}/publish` (existing endpoint, unchanged).
  2. `PublishService.run_publish_job` runs in the background (existing flow, unchanged up to the ingestion call).
  3. **New branch on `scenario.mode`:** for `master`, load all entities and facts for the scenario via `EntityRepo`/`FactRepo` (from `master-mode-data-model.spec.md`), transform into the extended `MemoryTemplateIngestRequest.entities`/`.facts` payload (§3.4), and call `ingest_scenario_template`. For `newbie`, behavior is exactly what exists today (`world_data`) — no change to that branch.
  4. Mock `ingest_scenario_template` stores whatever it's given (already true today) and returns a `template_space_id`, exactly as now.
  5. Playthrough creation's existing clone call (`POST /v1/memory/playthrough/{id}/init` equivalent, already implemented per ADR-7) is untouched by this spec.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Test: `pytest tests/services/test_publish_service.py -v` (from `apps/core-api/`)
- Lint/Format: `ruff format . && ruff check . --fix`

### 3.2. Testing Strategy & Conformance

- **Location:** `apps/core-api/tests/services/test_publish_service.py` (existing file — extend, don't fork).
- **Mocking:** `memory_client.ingest_scenario_template` is already a mock at the integration boundary; tests assert against the *request* built and passed to it (via a spy/mock of the client function), not against real memory-layer behavior — consistent with how `test_publish_service.py` presumably already tests the newbie-mode path.
- **Required cases:**
  - Master-mode publish: `run_publish_job` for a scenario with entities/facts calls `ingest_scenario_template` with `request.entities` and `request.facts` populated, and `request.world_data` empty/absent.
  - Newbie-mode publish: unchanged — `world_data` populated, `entities`/`facts` empty/absent. This is a regression test, not new behavior — it must keep passing exactly as it does today.
  - Hidden fact round-trip: the demo scenario's `the_warden vulnerable_to ember_sigil` fact (authored `hidden: true`) appears in the built request with `hidden: true` intact.
  - Empty master-mode scenario (0 entities, 0 facts): publish still succeeds, `ingest_scenario_template` called with empty lists, not skipped entirely — a scenario with no structured content yet is a valid (if sparse) master-mode scenario, not a publish error.
  - Publish failure path (existing `except Exception` branch in `run_publish_job`) is unaffected — a master-mode ingestion failure sets `publish_error` exactly like a newbie-mode one does today.

### 3.3. Project Structure & File Layout

**Files to modify:**
- `apps/core-api/app/models/memory.py` — extend `MemoryTemplateIngestRequest` with `entities: list[EntityIngestPayload] = Field(default_factory=list)` and `facts: list[FactIngestPayload] = Field(default_factory=list)`; add the two new payload models.
- `apps/core-api/app/services/publish_service.py` — branch `run_publish_job` on `scenario.mode` to build either the existing `world_data` request or the new entities/facts request; needs `EntityRepo`/`FactRepo` injected alongside the existing `ScenarioRepo`.
- `apps/core-api/app/integrations/memory_client.py` — no behavioral change required (the mock already just stores whatever it receives), but its module docstring should be updated to note it now also honors the entities/facts shape, keeping the "mock honors the real contract exactly" discipline documented accurately.
- `apps/core-api/tests/services/test_publish_service.py` — add the master-mode cases from §3.2.

### 3.4. Code Style & Interfaces

```python
# app/models/memory.py additions

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
```

```python
# app/services/publish_service.py — the mode branch inside run_publish_job

async def _build_ingest_request(
    scenario: Scenario, entity_repo: EntityRepo, fact_repo: FactRepo
) -> MemoryTemplateIngestRequest:
    if scenario.mode == "master":
        entities = await entity_repo.list_by_scenario(scenario.scenario_id)
        facts = await fact_repo.list_by_scenario(scenario.scenario_id)
        return MemoryTemplateIngestRequest(
            scenario_id=scenario.scenario_id,
            mode="master",
            entities=[_to_entity_payload(e) for e in entities],
            facts=[_to_fact_payload(f) for f in facts],
        )
    return MemoryTemplateIngestRequest(
        scenario_id=scenario.scenario_id,
        mode="newbie",
        world_data=scenario.world_data,
    )
```

### 3.5. Git & Review Workflow

- Branch: `feat/master-mode-memory-contract`
- Depends on `master-mode-data-model.spec.md` merged first (needs `EntityRepo.list_by_scenario`/`FactRepo.list_by_scenario`).
- Commit scope: one commit (this spec is small — the model extension, the service branch, and the tests belong together).
- PR checklist: existing newbie-mode publish tests still pass unmodified; the mock's docstring accurately describes what it now accepts.

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** keep `world_data` and `entities`/`facts` mutually exclusive per scenario mode; never let `memory_client.py` read Postgres directly — `publish_service.py` fetches via repos and hands the client a fully-built request object.
- ⚠️ **Ask First:** any change to the real (non-mock) memory layer's actual `when_active` filtering behavior — explicitly out of scope; this spec only shapes the contract, per the locked "mock stays a mock" decision.
- 🚫 **Never:** send both `world_data` and `entities`/`facts` populated on the same request; drop the `hidden` flag anywhere in the ingestion path.

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **Re-publishing an already-published master-mode scenario:** `run_publish_job` already handles re-publish (existing flow); this spec's only addition is that the entities/facts snapshot sent is always the *current* live table state at the moment of this publish, not a diff against the previous publish — consistent with `ADR-8`'s snapshot-at-playthrough-creation model (publish-time ingestion and playthrough-creation snapshotting are two independent, non-interacting mechanisms; this spec touches only the former).
- **Very large entity/fact counts:** no explicit pagination/batching added in this spec — `list_by_scenario` returns everything in one query, matching the scale the README explicitly designs for ("real scale, not simulated scale") without prematurely adding batching complexity the mock can't meaningfully exercise anyway.
- **Ingestion failure for a master-mode scenario:** identical degradation path to the existing newbie-mode failure branch in `run_publish_job` — `publish_error` is set, status reverts to `draft`/`publish_failed`, creator can retry. No new failure-handling code needed; the existing `except Exception` branch already covers this once the new branch is inside the same `try`.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Contract models):** Add `EntityIngestPayload`, `FactIngestPayload`, and the extended `MemoryTemplateIngestRequest` to `models/memory.py`. Verify: `ruff check` clean, existing memory model tests (if any) still pass.
- [ ] **Task 2 (Publish branch):** Modify `publish_service.py`'s `run_publish_job` to branch on `scenario.mode`, injecting `EntityRepo`/`FactRepo`. Verify: `pytest tests/services/test_publish_service.py`.
- [ ] **Task 3 (Docs + mock docstring):** Update `memory_client.py`'s module docstring to describe the entities/facts shape it now accepts. Verify: manual review only — no behavioral change to assert.
