# Spec: Master-Mode Maps — Location Graphs, Fog of War, and Reserved Position State

## 1. Objective & User Outcome

- **Problem Statement:** Master-mode scenarios have no spatial/geography concept. "Location" exists only as one `entity_type` value on the generic `entities` table (`master-mode-data-model.spec.md`) — a location is a named entity with free-form attributes, no coordinates, no connections, and no notion of "where the player currently is." Creators authoring a world with real geography (a dungeon, a city, a continent) have no way to draw it, and the turn pipeline has no concept of player position at all. This spec gives master-mode scenarios first-class **Maps**: images with pins tied to location entities, a scenario-wide connection graph between locations, and a reserved, system-maintained "current location" that the AI narrator can move the player through and that the Play surface reveals as fog of war.
- **User Story:** As a creator building a master-mode scenario, I want to draw one or more maps, pin my existing Location entities onto them with real coordinates, and connect locations with paths — so that during play, the narrator knows where the player is, can hint at nearby unexplored places, and the player sees their own explored-so-far map building up turn by turn, without me having to hand-wire any of the position tracking myself.
- **Success Criteria:**
  - A master-mode scenario can have zero or more `scenario_maps`, each with pins that reference existing `entity_type == "location"` entities (never a second, duplicated name/description).
  - Location entities can be connected in a scenario-wide graph (`map_connections`) whose edges may cross maps; edges are **advisory only** — narrative flavor for the AI narrator, never mechanically enforced movement.
  - Every scenario with ≥1 map has exactly one pin flagged as the starting location, enforced at the DB layer (at most one) and at publish time (at least one).
  - `current_location_id` and `discovered_location_ids` are **reserved, system-provisioned** state fields — a creator never manually adds them to `state_schema`, and any attempt to author those key names is rejected.
  - The player's location changes purely through their own freeform narration text, interpreted by Gemini via the existing generic `set_field` tool — **no new tool is added** to the fixed 4-tool set.
  - `discovered_location_ids` is maintained **deterministically by TRS infrastructure**, not by an AI tool call: whenever `current_location_id` changes, the new value is auto-appended if not already present. An AI tool call can never write `discovered_location_ids` directly.
  - The Play surface renders a fog-of-war map: only pins in `discovered_location_ids` are visible, and only edges between two discovered pins on the same map are drawn. There is no click-to-travel interaction — the map is a read-only view.
  - This feature is **master-mode only**: every Maps endpoint rejects a newbie-mode scenario with a domain error, not a silent no-op.
  - All new/modified files pass `ruff format . && ruff check . --fix` (Python) / `prettier --write . && eslint . --fix` (TypeScript) with zero warnings, respect Router → Service → Repository → DB layering, and every new endpoint has an integration test per CLAUDE.md.

## 2. Technical Architecture & Data Flow

- **Components Involved:** Core API (`app/routers/maps.py`, `app/services/map_service.py`, `app/repositories/map_repo.py`, new migration), Core API's existing `UploadService`/`storage_client.py` (reused, new prefix), Core API's `playthrough_service.py` (scenario_snapshot + initial-state seeding, already extended by two prior specs), TRS's `turn/pipeline.py` (one new guarded step), TRS's `turn/steps/ai_orchestrator.py` (one small prompt addition, no new tool), Frontend `shared/types/map.types.ts`, `features/studio/components/MapEditor/`, `features/play/components/MapViewer/`.
- **Depends on:** `master-mode-data-model.spec.md` (needs the `entities` table and its `entity_type = 'location'` values to pin against) and `master-mode-turn-pipeline.spec.md` (needs `game_state.py`'s `entity_ref`/`list` field support, and the working `ai_orchestrator` tool-call loop) merged first. Builds on, but does not modify, `master-mode-end-conditions.spec.md`'s pipeline shape.
- **Reference data:** "The Hollow Cairn" (`docs/specs/master-mode-demo-scenario.md`) has one dungeon-crawl location chain (cairn entrance → inner chamber, etc.) that this spec would model as a single map with 3–4 pins and 2–3 connections, `hollow_cairn_entrance` flagged as the start pin.

- **Sequence Flow — authoring (`POST /v1/scenarios/{id}/maps/{map_id}/pins`):**
  1. Creator has already created a `location`-type entity via the existing `EntityEditor` (unchanged).
  2. Creator opens the new "Maps" tab, uploads a map image (`POST /v1/uploads/scenario-map-image`, reusing `UploadService`), creates a `scenario_maps` row, then places a pin: client sends `{entity_id, x, y}`.
  3. Router validates request shape, delegates to `MapService.create_pin`.
  4. `MapService` runs `_ensure_scenario_owner` + `_ensure_master_mode` (rejects newbie-mode scenarios), confirms `entity_id` belongs to this scenario and has `entity_type == "location"` (else `MapPinInvalidEntityError`, 422), and — if `is_start_location: true` was requested — confirms no other pin in the scenario already holds that flag (else `MapStartLocationConflictError`, 422, a friendly pre-check before the DB's partial unique index would reject it anyway).
  5. `MapRepo` inserts the row.
  6. Service returns `MapPinResponse`.

- **Sequence Flow — playthrough creation:** `PlaythroughService.create_playthrough` (already touched by two prior specs) additionally: if the scenario has ≥1 map, (a) copies `maps`/`map_pins`/`map_connections` into `scenario_snapshot`, (b) injects `current_location_id` and `discovered_location_ids` into the snapshot's `state_schema` copy, (c) seeds `Playthrough.state["current_location_id"]` and `["discovered_location_ids"]` from the designated start pin's `entity_id`.

- **Sequence Flow — one master-mode turn, map-aware parts only** (full turn flow unchanged, see `master-mode-turn-pipeline.spec.md`):
  1. Player writes "I head north to the old watchtower."
  2. `ai_orchestrator` builds the system instruction as today, plus (new) one line naming any `map_connections` touching the current `current_location_id`, e.g. "Known paths from here: Old Watchtower (a steep goat trail), Riverside Camp." — pure flavor text, sourced from the frozen snapshot, never validated.
  3. Gemini calls `set_field(path="current_location_id", value="<watchtower_entity_id>")` — the existing generic tool, validated by the existing `state_validator`/`game_state.py` exactly like any other `entity_ref` field (is `watchtower_entity_id` a real entity ID? — already covered, no new code).
  4. **New `map_state_sync` step** runs after the tool-call loop, before `state_writer` persists: compares `working_state["current_location_id"]` to `loaded_state.state["current_location_id"]`; if changed and not already in `discovered_location_ids`, appends it in-place and adds `"discovered_location_ids"` to `mutated_paths`. This step never calls Gemini and is a no-op for scenarios without maps.
  5. `state_writer` persists the single updated state (location change + discovery update together, one write).
  6. Play surface's next state fetch reflects both the new `current_location_id` and the grown `discovered_location_ids` — the fog-of-war map updates without any extra request.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Core API build check (from `apps/core-api/`): `python3 -c "import fastapi, pydantic, sqlalchemy, alembic"`
- Core API test: `pytest tests/services/test_map_service.py tests/routers/test_map_router.py -v`
- Core API migration: `alembic upgrade head` (applies `007_master_mode_maps.py`); `alembic downgrade -1` must cleanly reverse it.
- TRS test: `pytest tests/turn/steps/test_map_state_sync.py tests/turn/test_pipeline_maps.py -v` (from `apps/turn-resolution-service/`)
- Frontend type-check: `npx tsc --noEmit` (from `apps/frontend/`)
- Frontend test: `npx vitest run src/features/studio/components/MapEditor src/features/play/components/MapViewer`
- Lint/Format: `ruff format . && ruff check . --fix` (Python) / `npx prettier --write . && npx eslint . --fix` (TypeScript)

### 3.2. Testing Strategy & Conformance

- **Location:** `apps/core-api/tests/{services,repositories,routers}/test_map_*.py`; `apps/turn-resolution-service/tests/turn/steps/test_map_state_sync.py`; `apps/frontend/src/features/{studio,play}/components/**/__tests__/` — mirroring source per CLAUDE.md.
- **Mocking:** Core API tests run against a real test Postgres (never mock the DB); TRS mocks Gemini via SDK-level mocks; frontend mocks network calls with `msw`.
- **Required cases:**
  - **Master-mode-only enforcement:** `POST /v1/scenarios/{newbie_id}/maps` returns `MapModeError` (422) for a newbie-mode scenario; the same request against a master-mode scenario succeeds.
  - **Pin entity validation:** creating a pin with an `entity_id` that is `entity_type == "character"` is rejected; one that belongs to a different scenario is rejected (`MapPinInvalidEntityError`).
  - **Start-pin uniqueness:** creating a second `is_start_location: true` pin in the same scenario (even on a different map) is rejected with `MapStartLocationConflictError`, both via the service pre-check and, if bypassed, via the DB partial unique index (assert the DB-level failure surfaces as a clean 500→domain-error mapping, not a raw `IntegrityError` leak).
  - **Connection validation:** a connection between two entities where one isn't `location`-type is rejected; a self-loop (`entity_id_a == entity_id_b`) is rejected; creating the same pair twice (in either order) is rejected as a duplicate.
  - **Cross-map connection:** a connection between a pin on Map A and a pin on Map B for the same scenario succeeds and is retrievable via the scenario-scoped `GET /v1/scenarios/{id}/map-connections`.
  - **Publish validation:** publishing a scenario with 1 map and 0 start pins is rejected with a domain error; publishing with exactly 1 start pin succeeds; publishing a scenario with 0 maps is unaffected (no new validation triggered).
  - **Reserved state keys:** `PATCH /v1/scenarios/{id}` with `state_schema` containing a `current_location_id` or `discovered_location_ids` key is rejected with `422`, regardless of whether the scenario has any maps yet.
  - **Snapshot + seeding:** creating a playthrough for a scenario with 1 map / 1 start pin produces a `scenario_snapshot` containing `maps`/`map_pins`/`map_connections`, a `state_schema` with the two injected fields, and initial `state.current_location_id == state.discovered_location_ids[0] == <start pin's entity_id>`.
  - **`map_state_sync`:** given `loaded_state.state["current_location_id"] == "a"` and a tool call that sets it to `"b"`, the synced state has `discovered_location_ids` containing both `"a"` (pre-existing) and `"b"` (newly appended), and `mutated_paths` includes `"discovered_location_ids"`. A second turn moving `"b" → "a"` does not duplicate `"a"` in the list.
  - **`map_state_sync` no-op:** a scenario with zero maps never runs this step (assert via a call-count spy on `pipeline.py`'s wiring) and a turn where `current_location_id` doesn't change makes no modification to `discovered_location_ids`.
  - **Reserved-path tool rejection:** a (mocked) Gemini function call proposing `set_field(path="discovered_location_ids", value=[...])` is rejected by the existing tool-validation layer with a function-response error, never reaching `working_state`.
  - **Prompt hint:** `ai_orchestrator`'s system instruction includes the "Known paths from here" line only when the current location has ≥1 connection in the snapshot; omits it entirely (no empty/awkward line) when it has none.
  - **`MapViewer` fog of war:** given `discovered_location_ids: ["a"]` and pins `["a", "b", "c"]` on the active map, only pin `"a"` renders; a connection `a↔b` is not drawn (b undiscovered); a connection `a↔a2` (both discovered, same map) is drawn.
  - **`MapViewer` no interaction:** clicking a rendered pin does not submit a turn or call any mutation hook (assert no network call fires on click).
  - **`MapEditor` scenario-type gating:** the "Maps" tab is present in `MasterModeStudioLayout` (master mode only) and does not appear anywhere in the newbie-mode `StudioDocumentLayout`.

### 3.3. Project Structure & File Layout

**Files to create (Core API):**
- `apps/core-api/app/db/models/scenario_map.py`, `app/db/models/map_pin.py`, `app/db/models/map_connection.py`
- `apps/core-api/app/models/map.py` (`MapCreate/Update/Response`, `MapPinCreate/Update/Response`, `MapConnectionCreate/Response`)
- `apps/core-api/app/repositories/map_repo.py`
- `apps/core-api/app/services/map_service.py`
- `apps/core-api/app/routers/maps.py`
- `apps/core-api/app/exceptions/map_exceptions.py`
- `apps/core-api/app/db/migrations/versions/007_master_mode_maps.py`
- `apps/core-api/tests/services/test_map_service.py`, `apps/core-api/tests/routers/test_map_router.py`, `apps/core-api/tests/repositories/test_map_repo.py`

**Files to modify (Core API):**
- `apps/core-api/app/db/models/__init__.py` — register `ScenarioMap`, `MapPin`, `MapConnection`.
- `apps/core-api/app/services/upload_service.py` — add `upload_map_image` (new `scenario-maps` prefix, same validation as `_upload_with_prefix`).
- `apps/core-api/app/routers/uploads.py` — add `POST /v1/uploads/scenario-map-image`.
- `apps/core-api/app/models/scenario.py` — `state_schema` validator rejects the reserved keys `current_location_id`/`discovered_location_ids`.
- `apps/core-api/app/services/scenario_service.py` — publish-time check: ≥1 map requires exactly one `is_start_location` pin.
- `apps/core-api/app/services/playthrough_service.py` — snapshot inclusion of `maps`/`map_pins`/`map_connections`; `state_schema` injection; initial-state seeding from the start pin.
- `apps/core-api/app/main.py` — register `maps.py` router.
- `apps/core-api/app/routers/playthroughs.py` (or wherever `GET /v1/playthroughs/{id}` lives) — add `map_data` to the response, sourced from `scenario_snapshot`.

**Files to create (TRS):**
- `apps/turn-resolution-service/app/turn/steps/map_state_sync.py`
- `apps/turn-resolution-service/tests/turn/steps/test_map_state_sync.py`

**Files to modify (TRS):**
- `apps/turn-resolution-service/app/turn/pipeline.py` — one guarded call to `map_state_sync.sync_discovered_locations(...)` after the tool-call loop's `working_state` is built, before `state_writer.write_turn`; update the module docstring (same style as its existing master-mode-step documentation).
- `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py` — add `_map_connection_hints(current_location_id, map_connections) -> str | None`, called from the existing system-instruction builder.
- `apps/turn-resolution-service/app/turn/steps/state_validator.py` (or `tool_handler.py`, wherever proposed mutations are checked pre-validation — verify exact file during implementation) — reject any tool-proposed `path` targeting `discovered_location_ids`.

**Files to create (Frontend):**
- `apps/frontend/src/shared/types/map.types.ts`
- `apps/frontend/src/features/studio/api/maps.api.ts`
- `apps/frontend/src/features/studio/hooks/{useMaps,useMapPins,useMapConnections,useUploadMapImage}.ts`
- `apps/frontend/src/features/studio/components/MapEditor/{MapList,MapCanvas,MapConnectionEditor}.tsx` (+ `.types.ts` each)
- `apps/frontend/src/features/play/components/MapViewer/MapViewer.tsx` (+ `.types.ts`)

**Files to modify (Frontend):**
- `apps/frontend/src/features/studio/components/Layout/MasterModeStudioLayout.types.ts` — add `{ id: "maps", label: "Maps" }` to `MASTER_MODE_TABS`.
- `apps/frontend/src/features/studio/components/Layout/MasterModeStudioLayout.tsx` — render `MapEditor` panel when `activeTab === "maps"`.
- `apps/frontend/src/features/play/pages/PlayPage.tsx` (or wherever the master-mode play surface composes its panels) — render `MapViewer` when the playthrough's `map_data.maps` is non-empty.

### 3.4. Code Style & Interfaces

#### Migration (`007_master_mode_maps.py`), following `003_master_mode_entities_facts.py`'s conventions exactly:

```python
def _create_scenario_maps_table() -> None:
    op.create_table(
        "scenario_maps",
        sa.Column("map_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("idx_scenario_maps_scenario_id", "scenario_maps", ["scenario_id"])

def _create_map_pins_table() -> None:
    op.create_table(
        "map_pins",
        sa.Column("pin_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("map_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenario_maps.map_id", ondelete="CASCADE"),
                   nullable=False),
        # Denormalized, same precedent as facts.scenario_id alongside
        # subject_entity_id — needed so "exactly one start pin" can be a
        # single scenario-scoped partial unique index, not a cross-map query.
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("is_start_location", sa.Boolean(),
                   server_default="false", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("idx_map_pins_map_id", "map_pins", ["map_id"])
    op.create_index(
        "idx_map_pins_one_start_per_scenario", "map_pins", ["scenario_id"],
        unique=True, postgresql_where=sa.text("is_start_location"),
    )

def _create_map_connections_table() -> None:
    op.create_table(
        "map_connections",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("entity_id_a", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("entity_id_b", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # Service always inserts the sorted-UUID pair; this single constraint
        # rejects both self-loops (a == b fails "<") and reversed duplicates.
        sa.CheckConstraint("entity_id_a < entity_id_b",
                            name="ck_map_connections_sorted_pair"),
        sa.UniqueConstraint("scenario_id", "entity_id_a", "entity_id_b",
                             name="uq_map_connections_pair"),
    )
    op.create_index("idx_map_connections_scenario_id", "map_connections", ["scenario_id"])
```

`upgrade()` calls all three helpers in this order; `downgrade()` reverses (drop `map_connections`, then `map_pins` [indexes first], then `scenario_maps` [index first]) — matching `001_initial_schema.py`'s drop-order discipline.

#### Pydantic schemas (`app/models/map.py`):

```python
import uuid
from pydantic import BaseModel, ConfigDict, Field

class MapCreate(BaseModel):
    name: str = Field(..., max_length=255)
    display_order: int = 0

class MapUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    image_url: str | None = None
    display_order: int | None = None

class MapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    map_id: uuid.UUID
    scenario_id: uuid.UUID
    name: str
    image_url: str | None
    display_order: int

class MapPinCreate(BaseModel):
    entity_id: uuid.UUID
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    is_start_location: bool = False

class MapPinUpdate(BaseModel):
    x: float | None = Field(default=None, ge=0.0, le=1.0)
    y: float | None = Field(default=None, ge=0.0, le=1.0)
    is_start_location: bool | None = None
    # entity_id is immutable after creation — matches EntityUpdate's
    # immutable-entity_type precedent; repin by deleting and recreating.

class MapPinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pin_id: uuid.UUID
    map_id: uuid.UUID
    entity_id: uuid.UUID
    x: float
    y: float
    is_start_location: bool

class MapConnectionCreate(BaseModel):
    entity_id_a: uuid.UUID
    entity_id_b: uuid.UUID
    label: str | None = None

class MapConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    connection_id: uuid.UUID
    scenario_id: uuid.UUID
    entity_id_a: uuid.UUID
    entity_id_b: uuid.UUID
    label: str | None
```

`MapService.create_connection` normalizes `(entity_id_a, entity_id_b)` into sorted-UUID order before constructing the ORM row — the API accepts either order from the client, the DB only ever sees one.

#### TRS `map_state_sync.py`:

```python
"""Deterministically maintains discovered_location_ids from current_location_id.

Runs after the tool-call loop's working_state is built, before state_writer
persists (pipeline.py is the sole sequencer — this file does not call
state_writer or ai_orchestrator itself). No AI involvement: discovery is
system-maintained infrastructure, not a tool call, per the locked decision.
"""

import structlog

logger = structlog.get_logger()

STATE_KEY_CURRENT_LOCATION = "current_location_id"
STATE_KEY_DISCOVERED_LOCATIONS = "discovered_location_ids"
EVENT_LOCATION_DISCOVERED = "map_location_discovered"


def sync_discovered_locations(
    previous_state: dict[str, object], working_state: dict[str, object]
) -> set[str]:
    """Mutate working_state in place; return the set of paths changed."""
    previous_location = previous_state.get(STATE_KEY_CURRENT_LOCATION)
    current_location = working_state.get(STATE_KEY_CURRENT_LOCATION)
    if current_location is None or current_location == previous_location:
        return set()

    discovered = working_state.setdefault(STATE_KEY_DISCOVERED_LOCATIONS, [])
    if current_location in discovered:
        return set()

    discovered.append(current_location)
    logger.info(EVENT_LOCATION_DISCOVERED, location_entity_id=current_location)
    return {STATE_KEY_DISCOVERED_LOCATIONS}
```

`pipeline.py` wiring (mirrors the existing `is_master_mode` branch style):

```python
if is_master_mode and loaded_state.scenario_snapshot.get("maps"):
    mutated_paths |= map_state_sync.sync_discovered_locations(
        loaded_state.state, working_state
    )
```

#### `ai_orchestrator.py` prompt-hint addition:

```python
def _map_connection_hints(
    current_location_id: str | None, map_connections: list[dict[str, object]]
) -> str | None:
    """Advisory-only flavor text; never validated or enforced."""
    if not current_location_id:
        return None
    touching = [
        c for c in map_connections
        if current_location_id in (c["entity_id_a"], c["entity_id_b"])
    ]
    if not touching:
        return None
    names = [
        f"{c['other_entity_name']}" + (f" ({c['label']})" if c.get("label") else "")
        for c in touching
    ]
    return "Known paths from here: " + ", ".join(names) + "."
```

(`other_entity_name` is resolved by the caller from the snapshot's `entities` list before this function runs — this function only formats, matching the single-responsibility rule.)

#### Frontend shared types (`shared/types/map.types.ts`):

```typescript
export interface ScenarioMap {
  map_id: string;
  scenario_id: string;
  name: string;
  image_url: string | null;
  display_order: number;
}

export interface MapPin {
  pin_id: string;
  map_id: string;
  entity_id: string;
  x: number; // 0-1, image-relative
  y: number;
  is_start_location: boolean;
}

export interface MapConnection {
  connection_id: string;
  scenario_id: string;
  entity_id_a: string;
  entity_id_b: string;
  label: string | null;
}
```

### 3.5. Git & Review Workflow

- Branch: `feat/master-mode-maps`
- Depends on `master-mode-data-model.spec.md` and `master-mode-turn-pipeline.spec.md` merged first.
- Commit scope: one commit for the migration + ORM models, one for the Core API map/pin/connection CRUD (service/repo/router/exceptions), one for the upload-service extension + reserved-key/publish validation, one for `playthrough_service.py` snapshot/seeding, one for the TRS `map_state_sync` step + `ai_orchestrator` prompt hint + pipeline wiring, one for the Studio `MapEditor` components, one for the Play `MapViewer` component.
- PR checklist: `alembic upgrade head && alembic downgrade -1` clean; every new endpoint has a passing integration test against a real test Postgres; `map_state_sync` has a dedicated unit test plus one pipeline-level integration test; existing newbie-mode and non-map master-mode turn tests still pass unmodified; `tsc --noEmit` and `eslint` clean; no `studio/`↔`play/` cross-imports (shared types only).

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** enforce `_ensure_master_mode` on every Maps endpoint; keep `current_location_id`/`discovered_location_ids` reserved (rejected in creator `state_schema`) unconditionally, not just when maps exist; run `map_state_sync` before `state_writer` so the discovery update lands in the same DB write; keep all SQL inside `repositories/`.
- ⚠️ **Ask First:** adding any mechanical enforcement of `map_connections` (turning "advisory only" into a hard travel restriction) — that reverses a locked product decision, not an implementation detail; adding click-to-travel to `MapViewer` — same reason.
- 🚫 **Never:** let a tool call write `discovered_location_ids` directly; let a pin reference an entity that isn't `entity_type == "location"` or that belongs to a different scenario; let `map_state_sync` call `ai_orchestrator` or `state_writer` itself; duplicate `ScenarioMap`/`MapPin`/`MapConnection` types between `studio/` and `play/` instead of importing from `shared/types/map.types.ts`.

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **Scenario with zero maps:** every map-aware code path (snapshot inclusion, `state_schema` injection, `map_state_sync`, the `ai_orchestrator` prompt hint, `MapViewer` rendering) is a guarded no-op — a master-mode scenario that never uses Maps behaves exactly as it does today, zero overhead, zero new state fields.
- **Deleting a location entity that is the start pin:** the pin cascades-deletes (`map_pins.entity_id` `ON DELETE CASCADE`) along with any `map_connections` touching it; the scenario now has a map with no start pin — allowed while in `draft`, but blocked at publish time by the existing "exactly one start pin" check, surfaced as a clear authoring warning rather than a silent gap.
- **Two locations satisfy narrative movement in the same turn (e.g. a "teleport then walk" combo action):** `set_field` on `current_location_id` can only be called once per meaningful change per the existing tool-call round-trip cap (`master-mode-turn-pipeline.spec.md`, 5 round-trips); `map_state_sync` only compares before/after the whole turn, so intermediate locations within one turn are not individually recorded as "discovered" — only the final location is. Documented as intentional: discovery tracks *where the player ends up*, not every intermediate tool call.
- **Cross-map connection where only one endpoint's map has been viewed:** `MapViewer` only draws an edge when both endpoints are in `discovered_location_ids` **and** share the active map being displayed; a discovered cross-map edge is not drawn at all in v1 (no "portal" indicator) — flagged as a known simplification, not solved by this spec, since visually linking two different map images/scales is a real design problem left for a follow-up.
- **Creator authors a `map_connections` label but the AI narrator ignores it:** acceptable — the hint is advisory prompt content, not a contract; no validation or retry logic wraps it, consistent with `narrator_persona`'s existing best-effort treatment elsewhere in the pipeline.
- **Large numbers of pins/connections in the Studio editor:** no pagination in this spec, matching `master-mode-studio-ui.spec.md`'s existing posture for entity/fact pickers — a searchable combobox is the fix if this becomes a real problem, not solved here.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Migration & ORM):** Write `007_master_mode_maps.py` (`scenario_maps`, `map_pins`, `map_connections`) and the three new `db/models/*.py` ORM classes; register in `db/models/__init__.py`. Verify: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.
- [ ] **Task 2 (Core API CRUD):** Implement `models/map.py`, `repositories/map_repo.py`, `services/map_service.py` (including `_ensure_master_mode`, pin-entity validation, start-pin pre-check, connection sorted-pair normalization), `routers/maps.py`, `exceptions/map_exceptions.py`; register router in `main.py`. Verify: `pytest tests/services/test_map_service.py tests/routers/test_map_router.py`.
- [ ] **Task 3 (Upload + reserved keys + publish validation):** Add `upload_map_image` to `UploadService` + `POST /v1/uploads/scenario-map-image`; add reserved-key rejection to `models/scenario.py`'s `state_schema` validation; add the "≥1 map needs exactly 1 start pin" publish check to `scenario_service.py`. Verify: targeted unit tests for each of the three checks.
- [ ] **Task 4 (Snapshot + state seeding):** Extend `playthrough_service.py`'s `create_playthrough` to include map data in `scenario_snapshot`, inject the two reserved `state_schema` fields, and seed initial state from the start pin; extend the playthrough response with `map_data`. Verify: a snapshot/seeding fixture test against a 1-map/1-start-pin scenario.
- [ ] **Task 5 (TRS discovery sync):** Implement `turn/steps/map_state_sync.py`; wire into `pipeline.py` (guarded, master-mode + maps-present); add the reserved-path rejection for `discovered_location_ids` in the tool-validation layer. Verify: `pytest tests/turn/steps/test_map_state_sync.py tests/turn/test_pipeline_maps.py`.
- [ ] **Task 6 (Narrator flavor hint):** Add `_map_connection_hints` to `ai_orchestrator.py`'s prompt builder. Verify: `pytest tests/turn/steps/test_ai_orchestrator.py` (hint-present and hint-absent cases).
- [ ] **Task 7 (Studio MapEditor):** Implement `shared/types/map.types.ts`, `api/maps.api.ts`, `hooks/{useMaps,useMapPins,useMapConnections,useUploadMapImage}.ts`, `components/MapEditor/{MapList,MapCanvas,MapConnectionEditor}.tsx`; add the "Maps" tab to `MasterModeStudioLayout`. Verify: `npx vitest run src/features/studio/components/MapEditor`; manual dev-server walkthrough placing pins and connections on a real scenario.
- [ ] **Task 8 (Play MapViewer):** Implement `components/MapViewer/MapViewer.tsx` (fog-of-war filtering, active-map selection, no click handling); wire into the master-mode play surface. Verify: `npx vitest run src/features/play/components/MapViewer`; manual playthrough confirming the map grows as `current_location_id` changes across turns.
