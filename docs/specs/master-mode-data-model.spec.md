# Spec: Master-Mode Data Model & Core-API Authoring Endpoints

## 1. Objective & User Outcome

- **Problem Statement:** Master mode's DB columns exist only as unstructured JSONB on `Scenario`, and every entity/fact/condition-adjacent authoring file (`models/entity.py`, `models/fact.py`, `models/condition.py`, their repos, services, and routers) is a 0-byte stub. There is no way for a creator to author a structured world, and no schema an AI narrator's tool calls could ever validate against. This spec gives master mode real, queryable, FK-integral storage and a full CRUD authoring API.
- **User Story:** As a creator building a master-mode scenario, I want to define entities (with their own typed attributes like HP), facts connecting them (including secret ones), active conditions (including ones that directly mutate state), win/lose conditions with multiple named outcomes, and hard world-rule invariants — all through a REST API that rejects broken references immediately — so that my structured world is exactly as strict as I intend it to be, with nothing reinterpreted by an LLM.
- **Success Criteria:**
  - `entities`, `facts`, `end_conditions`, and `rule_invariants` exist as first-class Postgres tables with FK integrity; `scenario_conditions` gains the columns needed for Effect C.
  - Full CRUD for all five resource types, mounted and reachable, replacing every currently-empty stub file listed in §3.3.
  - Deleting an entity cascades to every fact referencing it as subject or object (per the README's stated behavior).
  - A fact's `object` is exactly one of an entity reference or a typed literal — never both, never neither — enforced at the DB and Pydantic layers.
  - `POST`/`PATCH` on facts, conditions, and invariants that reference a nonexistent state-schema field or entity return a `422` domain error before anything is persisted (real-time-validation-capable backend; the Studio spec wires this into inline UI feedback).
  - All new/filled files pass `ruff format . && ruff check . --fix` with zero warnings and respect the Router → Service → Repository → DB layering — no SQL outside `repositories/`, no business logic in routers.
  - Every endpoint has an integration test under `tests/routers/` and `tests/services/`, run against a real test Postgres instance (no DB mocking), per CLAUDE.md.

## 2. Technical Architecture & Data Flow

- **Components Involved:** FastAPI routers (`app/routers/{entities,facts,conditions,end_conditions,invariants}.py`), one service and one repository per domain, SQLAlchemy async ORM models, Alembic migration, Pydantic v2 request/response schemas. No AI calls, no streaming — this is Core API, stateless request/response only, matching every other domain already in this service.
- **Reference data:** every example below is drawn from `docs/specs/master-mode-demo-scenario.md` ("The Hollow Cairn"). Read that file first if any example here is unclear.
- **Sequence Flow (example: `POST /v1/scenarios/{id}/facts`):**
  1. Client sends the fact payload (`subject_entity_id`, `predicate`, one of `object_entity_id`/`object_literal`, optional `when_active`, `hidden`).
  2. Router validates the request shape via Pydantic and delegates to `FactService`.
  3. `FactService` loads the scenario's `state_schema` (to validate any `when_active` expression's field references) and confirms `subject_entity_id`/`object_entity_id` belong to entities owned by this scenario — raising `FactInvalidReferenceError` (422) if not.
  4. `FactRepo` inserts the row; a DB `CHECK` constraint is the last-line guarantee that exactly one of `object_entity_id`/`object_literal` is set.
  5. Service returns the created fact as a `FactResponse`.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Build/dependency check (from `apps/core-api/`): `python3 -c "import fastapi, pydantic, sqlalchemy, alembic"`
- Test: `pytest tests/services/test_entity_service.py tests/services/test_fact_service.py tests/services/test_condition_service.py tests/services/test_end_condition_service.py tests/services/test_invariant_service.py tests/routers/test_entity_router.py tests/routers/test_fact_router.py tests/routers/test_condition_router.py tests/routers/test_end_condition_router.py tests/routers/test_invariant_router.py -v`
- Migration: `alembic upgrade head` (applies `003_master_mode_entities_facts.py`); `alembic downgrade -1` must cleanly reverse it.
- Lint/Format: `ruff format . && ruff check . --fix`

### 3.2. Testing Strategy & Conformance

- **Location:** `apps/core-api/tests/services/`, `apps/core-api/tests/repositories/`, `apps/core-api/tests/routers/` — mirroring source files per CLAUDE.md (e.g. `tests/services/test_entity_service.py` tests `app/services/entity_service.py`).
- **Required cases (per resource, adapted to the resource's shape):**
  - Happy-path create/get/update/delete.
  - Cross-scenario isolation: an entity/fact/condition belonging to scenario A is not readable/writable via scenario B's sub-resource path.
  - `FactInvalidReferenceError`: creating a fact whose `subject_entity_id` or `object_entity_id` doesn't exist, or belongs to a different scenario.
  - Fact object exclusivity: request with both `object_entity_id` and `object_literal` set (or neither) is rejected with `422` before any DB write.
  - Entity deletion cascade: deleting an entity referenced by 2+ facts (as subject or object) removes those facts too; verify via a direct repo-level fact count check post-delete.
  - `hidden` fact round-trip: a fact created with `hidden: true` is returned as such on `GET`, and is excluded from whatever "player-facing fact list" endpoint/serializer this spec exposes (there is no such endpoint in this spec — hidden filtering for player-facing surfaces belongs to `master-mode-memory-contract.spec.md` and `master-mode-turn-pipeline.spec.md`; this spec's test only confirms the flag persists correctly).
  - Invariant/condition expression validation: an expression referencing a `field` path not present in the scenario's `state_schema` (or, for entity-scoped invariants, not in the target entity's `attributes_schema`) is rejected at write time with a domain error, not silently accepted.
  - End condition multi-outcome: two end conditions with `outcome_tag: "win"` on the same scenario are both persisted and independently retrievable (not deduplicated or merged).
  - Migration reversibility: `alembic upgrade head` then `alembic downgrade -1` leaves the schema byte-identical to pre-migration (checked via `alembic check` or a schema diff in CI, matching whatever pattern `002_bookmarks_and_reviews.py`'s test coverage already uses).

### 3.3. Project Structure & File Layout

**Files to fill in (currently 0-byte stubs):**
- `apps/core-api/app/models/entity.py`
- `apps/core-api/app/models/fact.py`
- `apps/core-api/app/models/condition.py`
- `apps/core-api/app/repositories/entity_repo.py`
- `apps/core-api/app/repositories/fact_repo.py`
- `apps/core-api/app/repositories/condition_repo.py`
- `apps/core-api/app/services/entity_service.py`
- `apps/core-api/app/services/fact_service.py`
- `apps/core-api/app/services/condition_service.py`
- `apps/core-api/app/routers/entities.py`
- `apps/core-api/app/routers/facts.py`
- `apps/core-api/app/routers/conditions.py`

**Files to create (new — end_conditions and invariants were JSONB/nonexistent before this spec):**
- `apps/core-api/app/db/models/entity.py`, `apps/core-api/app/db/models/fact.py`, `apps/core-api/app/db/models/end_condition.py`, `apps/core-api/app/db/models/rule_invariant.py`
- `apps/core-api/app/models/end_condition.py`, `apps/core-api/app/models/invariant.py`
- `apps/core-api/app/repositories/end_condition_repo.py`, `apps/core-api/app/repositories/invariant_repo.py`
- `apps/core-api/app/services/end_condition_service.py`, `apps/core-api/app/services/invariant_service.py`
- `apps/core-api/app/routers/end_conditions.py`, `apps/core-api/app/routers/invariants.py`
- `apps/core-api/app/exceptions/entity_exceptions.py`, `apps/core-api/app/exceptions/fact_exceptions.py`, `apps/core-api/app/exceptions/condition_exceptions.py`
- `apps/core-api/app/db/migrations/versions/003_master_mode_entities_facts.py`
- `apps/core-api/tests/services/test_entity_service.py` (+ one per new domain, mirrored in `tests/routers/`)

**Files to modify:**
- `apps/core-api/app/db/models/__init__.py` — register `Entity`, `Fact`, `EndCondition`, `RuleInvariant` in `__all__` and imports (needed for Alembic autogenerate/metadata discovery, same pattern as the existing five entries).
- `apps/core-api/app/db/models/scenario_condition.py` — add `state_mutation: dict[str, object] | None` (JSONB, nullable) for Effect C.
- `apps/core-api/app/db/models/scenario.py` and `apps/core-api/app/models/scenario.py` — add `opening_scene`, `narration_font`, `action_chips`, `setup_archetypes` (ORM columns + the corresponding `ScenarioCreate`/`ScenarioUpdate`/`ScenarioResponse` Pydantic fields), consumed by `master-mode-studio-ui.spec.md`.
- `apps/core-api/app/main.py` — register the five new/filled routers.

### 3.4. Code Style & Interfaces

#### Migration (`003_master_mode_entities_facts.py`) — new tables, snake_case, `gen_random_uuid()` PKs matching `001_initial_schema.py`'s conventions exactly:

```python
def _create_entities_table() -> None:
    op.create_table(
        "entities",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("entity_type", sa.String(length=30),
                   sa.CheckConstraint(
                       "entity_type IN ('character', 'location', 'item', "
                       "'faction', 'organization')",
                       name="ck_entities_entity_type"),
                   nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.Text()),
                   server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("obtainable", sa.Boolean(), nullable=True),
        sa.Column("attributes_schema", postgresql.JSONB(astext_type=sa.Text()),
                   server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("narrator_instruction", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

def _create_facts_table() -> None:
    op.create_table(
        "facts",
        sa.Column("fact_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("subject_entity_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("predicate", sa.String(length=100), nullable=False),
        sa.Column("object_entity_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
                   nullable=True),
        sa.Column("object_literal", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.String(length=100), nullable=True),
        sa.Column("when_active", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("superseded_fact_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("facts.fact_id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()),
                   server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "(object_entity_id IS NOT NULL) != (object_literal IS NOT NULL)",
            name="ck_facts_object_exclusive",
        ),
    )
    op.create_index("idx_facts_scenario_id", "facts", ["scenario_id"])
    op.create_index("idx_facts_subject_entity_id", "facts", ["subject_entity_id"])

def _create_end_conditions_table() -> None:
    op.create_table(
        "end_conditions",
        sa.Column("end_condition_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("condition_expression", postgresql.JSONB(astext_type=sa.Text()),
                   server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("outcome_tag", sa.String(length=10),
                   sa.CheckConstraint("outcome_tag IN ('win', 'lose')",
                                       name="ck_end_conditions_outcome_tag"),
                   nullable=False),
        sa.Column("outcome_title", sa.String(length=255), nullable=False),
        sa.Column("outcome_text", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), server_default="false", nullable=False),
        # Explicit creator-controlled precedence for "first match wins"
        # evaluation (master-mode-end-conditions.spec.md) — NOT createdAt
        # order, since the Studio's reorder UI (master-mode-studio-ui.spec.md)
        # must let a creator change precedence without deleting and
        # recreating rows. Lower value evaluates first.
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("idx_end_conditions_scenario_priority", "end_conditions",
                     ["scenario_id", "priority"])

def _create_rule_invariants_table() -> None:
    op.create_table(
        "rule_invariants",
        sa.Column("invariant_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("invariant_expression", postgresql.JSONB(astext_type=sa.Text()),
                   server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("applies_to", sa.String(length=255), nullable=False),
        sa.Column("narrator_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

def _add_effect_c_column_to_scenario_conditions() -> None:
    op.add_column(
        "scenario_conditions",
        sa.Column("state_mutation", postgresql.JSONB(astext_type=sa.Text()),
                   nullable=True),
    )

def _add_studio_authoring_columns_to_scenarios() -> None:
    """Small, independent creator-power fields locked in during the Q&A pass
    that don't warrant their own migration — added here alongside the other
    master-mode schema work. All nullable/defaulted: safe no-op for existing
    (including newbie-mode) scenarios."""
    op.add_column("scenarios", sa.Column("opening_scene", sa.Text(), nullable=True))
    op.add_column("scenarios", sa.Column(
        "narration_font", sa.String(length=50), nullable=True))
    op.add_column("scenarios", sa.Column(
        "action_chips", postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"), nullable=False))
    op.add_column("scenarios", sa.Column(
        "setup_archetypes", postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"), nullable=False))
```

`upgrade()` calls all seven helpers above (including `_add_studio_authoring_columns_to_scenarios`); `downgrade()` reverses in strict reverse order: drop the four `scenarios` columns, then `state_mutation`, then `rule_invariants`, `end_conditions` (index first), `facts` (indexes first), `entities` — matching `001_initial_schema.py`'s drop-order discipline.

#### Pydantic schemas (`app/models/entity.py`), matching `scenario.py`'s Create/Update/Response split:

```python
import uuid
from pydantic import BaseModel, ConfigDict, Field

ENTITY_TYPES = ("character", "location", "item", "faction", "organization")

class AttributeFieldSchema(BaseModel):
    type: str = Field(..., pattern="^(string|number|boolean|enum)$")
    initial: object = None
    min: float | None = None
    max: float | None = None
    label: str | None = None

class EntityCreate(BaseModel):
    entity_type: str = Field(..., pattern="^(" + "|".join(ENTITY_TYPES) + ")$")
    canonical_name: str = Field(..., max_length=255)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    obtainable: bool | None = None
    attributes_schema: dict[str, AttributeFieldSchema] = Field(default_factory=dict)
    narrator_instruction: str | None = None

class EntityUpdate(BaseModel):
    canonical_name: str | None = Field(default=None, max_length=255)
    aliases: list[str] | None = None
    description: str | None = None
    obtainable: bool | None = None
    attributes_schema: dict[str, AttributeFieldSchema] | None = None
    narrator_instruction: str | None = None
    # entity_type is immutable after creation — changing it would silently
    # invalidate every fact/condition that assumed the old type.

class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_id: uuid.UUID
    scenario_id: uuid.UUID
    entity_type: str
    canonical_name: str
    aliases: list[str]
    description: str | None
    obtainable: bool | None
    attributes_schema: dict[str, object]
    narrator_instruction: str | None
```

`app/models/fact.py` follows the same shape with a service-level validator (not a Pydantic field validator, since it needs a DB lookup) enforcing exactly one of `object_entity_id`/`object_literal`.

### 3.5. Git & Review Workflow

- Branch: `feat/master-mode-data-model`
- Commit scope: one commit for the migration + ORM models, one per domain (entity, fact, condition/Effect-C, end_condition, invariant) for the Pydantic/service/repo/router layer, matching how `scenario-crud.spec.md` and `initial-schema-migration.spec.md` were built.
- PR checklist: migration runs clean up and down against a fresh local Postgres; every new endpoint has a passing integration test; `ruff check` zero warnings; no router imports a repository directly.

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** validate entity/fact/condition/invariant expression field-references against the owning scenario's `state_schema`/entity `attributes_schema` before persisting; keep all SQL inside `repositories/`; run the targeted test suite before reporting done.
- ⚠️ **Ask First:** any change to the `001_initial_schema.py` migration itself (this spec only adds a new migration, `003_...`, never edits `001` or `002`); changing the fixed `entity_type` taxonomy list once scenarios exist against it.
- 🚫 **Never:** allow a fact to reference an entity from a different scenario; allow both `object_entity_id` and `object_literal` to be set; put SQL in a service or router file; skip the cascading-delete test for entities.

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **Entity deletion mid-authoring:** deleting an entity that's the `object_entity_id` of 40 facts must cascade in one transaction, not 40 round-trips — rely on the DB-level `ON DELETE CASCADE`, don't hand-roll cascade logic in the service layer.
- **Circular `superseded_fact_id`:** reject a fact update that would make `superseded_fact_id` point back to itself, directly or transitively, with a domain error — a self-referencing supersession chain would break any future consumer walking it.
- **Invariant referencing a deleted state-schema field:** if a creator removes a `state_schema` field that an existing `rule_invariants` row references, the invariant is not silently orphaned — `PATCH /v1/scenarios/{id}` (already-existing endpoint, out of this spec's direct scope but noted here) should be made aware in a follow-up that state_schema edits need the same reference-check this spec applies to *creating* invariants; flag this as a known gap for `master-mode-studio-ui.spec.md`'s real-time validation to close on the frontend side, since the backend check at invariant-creation-time doesn't protect against edits made afterward to the field it depends on.
- **Large `attributes_schema`/`when_active` payloads:** no explicit size cap in this spec; rely on Postgres's own JSONB limits and standard request body size middleware already in place for the service — do not add a bespoke limit unless real usage shows it's needed.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Migration & ORM):** Write `003_master_mode_entities_facts.py` (entities, facts, end_conditions, rule_invariants, `scenario_conditions.state_mutation`) and the four new `db/models/*.py` ORM classes; update `db/models/__init__.py`. Verify: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all succeed against a local Postgres.
- [ ] **Task 2 (Entities domain):** Fill `models/entity.py`, `repositories/entity_repo.py`, `services/entity_service.py`, `routers/entities.py`, `exceptions/entity_exceptions.py`. Verify: `pytest tests/services/test_entity_service.py tests/routers/test_entity_router.py`.
- [ ] **Task 3 (Facts domain):** Fill `models/fact.py`, `repositories/fact_repo.py`, `services/fact_service.py`, `routers/facts.py`, `exceptions/fact_exceptions.py`, including the object-exclusivity and cross-scenario-reference checks. Verify: `pytest tests/services/test_fact_service.py tests/routers/test_fact_router.py`.
- [ ] **Task 4 (Conditions + Effect C):** Fill `models/condition.py`, `repositories/condition_repo.py`, `services/condition_service.py`, `routers/conditions.py`, `exceptions/condition_exceptions.py`, including `state_mutation` read/write. Verify: `pytest tests/services/test_condition_service.py tests/routers/test_condition_router.py`.
- [ ] **Task 5 (End conditions):** Create `models/end_condition.py`, `db models`, repo, service, router — multi-outcome support (two `win`-tagged rows on one scenario). Verify: `pytest tests/services/test_end_condition_service.py tests/routers/test_end_condition_router.py`.
- [ ] **Task 6 (Rule invariants):** Create `models/invariant.py`, repo, service, router — expression-reference validation against `state_schema`/entity `attributes_schema`. Verify: `pytest tests/services/test_invariant_service.py tests/routers/test_invariant_router.py`.
- [ ] **Task 7 (Wiring):** Register all five routers in `main.py`; run the full `apps/core-api` test suite and `ruff check .` clean.
