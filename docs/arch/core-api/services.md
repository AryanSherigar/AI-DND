# Core API Architecture — Services & Business Logic

This document details the business logic layer across all 17 service modules in `apps/core-api/app/services/`. The service layer sits between the routers and repositories, coordinating entity transactions, permission checks, expression tree validations, and asynchronous background tasks.

---

## 1. Overview & Service Layer Rules

In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md):
- **Services call repositories only.** No direct database queries, raw SQL, or bypassing the repository layer.
- **Single Responsibility & Function Length**: Functions are under 30 lines; operations performing I/O do not mix data transformation logic.
- **Explicit Domain Exceptions**: Services raise strongly-typed exceptions from `app/exceptions/` (e.g., `ScenarioNotFoundError`, `ConditionValidationError`).
- **Structured Logging**: Services log business milestones and audit events using `structlog` (`log_audit_event`). Repositories do not log.

---

## 2. Service Profiles

### `apps/core-api/app/services/scenario_service.py`
- **Purpose & Layer:** Core scenario authoring lifecycle, cloning, bookmarks, and discovery service.
- **Key Methods & Logic:**
  - `create_scenario(user_id, data)`: Initializes draft scenario with default state schema, genre tags, and narrator persona.
  - `get_scenario(scenario_id, user_id)`: Fetches scenario, checking access permissions (drafts require author match; published scenarios are public).
  - `update_scenario(scenario_id, user_id, data)`: Modifies draft fields. Enforces immutability once published.
  - `delete_scenario(scenario_id, user_id)`: Soft-archives scenarios to preserve active playthrough history.
  - `duplicate_for_playtest(scenario_id, user_id)`: Clones a scenario, its entities, facts, conditions, and maps into a temporary private draft for author testing.
  - `list_scenarios(...)`: Applies search, genre tag filters, complexity tiers, user bookmarks, and sorting (`trending`, `recent`, `rating`).
  - `toggle_bookmark(user_id, scenario_id)`: Adds or removes scenario from the user's bookmarks list.
  - `list_reviews(...)` / `add_review(user_id, scenario_id, data)`: Validates that the player has participated in at least 10 turns in a playthrough before permitting review submission.
- **Dependencies & Interactions:** Calls `ScenarioRepo`.
- **Architecture Rules & Invariants:** Never directly invokes the memory layer (delegated to `PublishService`).

### `apps/core-api/app/services/publish_service.py`
- **Purpose & Layer:** Two-phase publishing coordinator for scenarios, enforcing integrity constraints and queuing asynchronous world-fact memory ingestion (ADR-010).
- **Key Methods & Logic:**
  - `start_publish(scenario_id, user_id)`: Synchronous phase 1. Validates ownership, checks required fields (opening scene, content tags in `{"all-ages", "teen", "mature"}`), validates map connections, and transitions scenario status to `"publishing"`.
  - `run_publish_job(scenario_id, session_factory)`: Asynchronous phase 2 executed via FastAPI `BackgroundTasks`. Uses dedicated `AsyncSession` to extract all scenario entities and facts, constructs `MemoryTemplateIngestRequest`, sends payload to the Memory Layer via `memory_client`, and flips status to `"published"`. Emits audit log events (`scenario_publish_started`, `scenario_publish_completed`).
- **Dependencies & Interactions:** Calls `ScenarioRepo`, `EntityRepo`, `FactRepo`, `MapRepo`, and `app/integrations/memory_client.py`.
- **Architecture Rules & Invariants:** Background task must use its own session factory (`async_sessionmaker`), as the originating request session terminates upon HTTP response.

### `apps/core-api/app/services/playthrough_service.py`
- **Purpose & Layer:** Playthrough instance lifecycle, participation enrollment, and state management.
- **Key Methods & Logic:**
  - `create_playthrough(user_id, data)`: Instantiates a new playthrough from a published scenario, initializing participants and copying default state schemas.
  - `get_playthrough(playthrough_id, user_id)`: Retrieves playthrough and participant state.
  - `join_playthrough(playthrough_id, user_id, character_data)`: Enrolls a new player into a multiplayer session.
  - `update_character_fields(playthrough_id, user_id, fields)`: Updates dynamic player state attributes.
  - `abandon_playthrough(playthrough_id, user_id)`: Marks playthrough status as abandoned.
- **Dependencies & Interactions:** Calls `PlaythroughRepo`, `ParticipantRepo`, and `ScenarioRepo`.

### `apps/core-api/app/services/entity_service.py`
- **Purpose & Layer:** Master Mode entity authoring and validation service.
- **Key Methods & Logic:**
  - Validates and creates NPCs, items, locations, and faction entities.
  - Ensures entity attribute keys conform to scenario entity type schemas and archetype definitions.
- **Dependencies & Interactions:** Calls `EntityRepo` and `ScenarioRepo`.

### `apps/core-api/app/services/scenario_entity_type_service.py`
- **Purpose & Layer:** Custom entity taxonomy management service.
- **Key Methods & Logic:** Manages custom archetype schemas (e.g. "Weapon", "Spell", "Faction") and attribute rules.
- **Dependencies & Interactions:** Calls `ScenarioEntityTypeRepo`.

### `apps/core-api/app/services/fact_service.py`
- **Purpose & Layer:** Scenario world lore and knowledge base management service.
- **Key Methods & Logic:** CRUD operations for static world facts. Validates subject-predicate-object structure.
- **Dependencies & Interactions:** Calls `FactRepo`.

### `apps/core-api/app/services/condition_service.py`
- **Purpose & Layer:** Dynamic condition logic authoring service.
- **Key Methods & Logic:** Validates state condition trigger expressions against scenario `state_schema` and entity schemas before storage.
- **Dependencies & Interactions:** Calls `ConditionRepo`, `ScenarioRepo`, `EntityRepo`, and `expression_validation.py`.

### `apps/core-api/app/services/end_condition_service.py`
- **Purpose & Layer:** Win/loss outcome authoring service.
- **Key Methods & Logic:** Validates boolean end-condition expression trees and terminal narrative prompts.
- **Dependencies & Interactions:** Calls `EndConditionRepo`, `ScenarioRepo`, and `expression_validation.py`.

### `apps/core-api/app/services/invariant_service.py`
- **Purpose & Layer:** Master Mode rule invariant authoring service.
- **Key Methods & Logic:** Validates state boundary expressions (e.g., `hp >= 0`, `gold <= 9999`) to prevent invalid AI game mutations.
- **Dependencies & Interactions:** Calls `InvariantRepo`, `ScenarioRepo`, and `expression_validation.py`.

### `apps/core-api/app/services/expression_validation.py`
- **Purpose & Layer:** Shared recursive AST validator for condition and invariant expressions.
- **Key Methods & Logic:**
  - `validate_expression_field_references(expression, state_schema, entities_by_id, error_factory)`: Recursively walks logical connectives (`AND`, `OR`, `NOT`) and verifies that any referenced `field` path exists either in the scenario `state_schema` or in an entity's `attributes_schema`.
  - Injects caller's domain exception via `error_factory` to maintain typed error boundaries.
- **Dependencies & Interactions:** Pure business logic; zero I/O or repository dependencies.

### `apps/core-api/app/services/map_service.py`
- **Purpose & Layer:** Spatial cartography service managing scenario maps, interactive pins, and node connections.
- **Key Methods & Logic:**
  - Manages image dimensions, fog-of-war settings, pin coordinates (`x`, `y`), linked entity references, and bidirectional map edges.
  - `validate_maps_for_publish(scenario_id)`: Enforces that published scenarios with maps have valid connections and pins.
- **Dependencies & Interactions:** Calls `MapRepo`.

### `apps/core-api/app/services/auth_service.py`
- **Purpose & Layer:** User synchronization and identity profile service.
- **Key Methods & Logic:**
  - `sync_firebase_user(token_payload)`: Upserts a local `User` record matching the Firebase UID, email, and display name.
  - `update_profile(user_id, data)`: Modifies user bio, preferred genres, and UI theme preferences.
- **Dependencies & Interactions:** Calls `UserRepo`.

### `apps/core-api/app/services/user_service.py`
- **Purpose & Layer:** Public creator profile and social statistics aggregation service.
- **Key Methods & Logic:** Compiles creator profile data, published scenario lists, playthrough stats, and community rating averages.
- **Dependencies & Interactions:** Calls `UserRepo` and `ScenarioRepo`.

### `apps/core-api/app/services/share_service.py`
- **Purpose & Layer:** Secure sharing link creation and verification service.
- **Key Methods & Logic:** Generates cryptographically signed share tokens for spectators or multiplayer invites with expiration timestamps.
- **Dependencies & Interactions:** Calls `ShareRepo`.

### `apps/core-api/app/services/upload_service.py`
- **Purpose & Layer:** Asset upload authorization and storage orchestration service.
- **Key Methods & Logic:** Validates content type (PNG, JPEG, WebP) and file size (< 5MB), generating signed PUT URLs for Google Cloud Storage.
- **Dependencies & Interactions:** Calls `app/integrations/storage_client.py`.

### `apps/core-api/app/services/rating_service.py`
- **Purpose & Layer:** Dedicated review calculations and aggregate score calculation service.
- **Key Methods & Logic:** Recalculates Bayesian weighted ratings and review distribution counts for scenarios.
- **Dependencies & Interactions:** Calls `ScenarioRepo`.

### `apps/core-api/app/services/log_ingestion_service.py`
- **Purpose & Layer:** Client-side telemetry and error log ingestion service.
- **Key Methods & Logic:** Validates and forwards browser-side runtime errors and performance metrics to backend structured logging sinks.
- **Dependencies & Interactions:** Pure processing and structured logging dispatch.
