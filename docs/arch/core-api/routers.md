# Core API Architecture — Routers & HTTP Endpoints

This document details all 15 router modules located in `apps/core-api/app/routers/`. Routers handle incoming HTTP requests, dependency injection of database sessions and domain services, request authentication, and response serialization.

---

## 1. Overview & Router Responsibilities

In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md):
- **Routers call services only.** No repository calls, direct database queries, or SQL generation.
- **Dependency Injection**: Each router declares service factory functions (e.g. `get_scenario_service`) receiving `Annotated[AsyncSession, Depends(get_db_session)]`.
- **Authentication**: Endpoints declare `user: Annotated[User, Depends(get_current_user)]` for mandatory auth or `get_optional_current_user` for public/discovery endpoints.

---

## 2. Router File Profiles

### `apps/core-api/app/routers/scenarios.py`
- **Purpose & Layer:** Primary authoring, discovery, and social hub controller for Scenarios (`/v1/scenarios`).
- **Key Endpoints & Exports:**
  - `POST /v1/scenarios`: Creates draft scenario (`ScenarioCreate`).
  - `GET /v1/scenarios/{id}`: Retrieves scenario metadata, author details, and published status.
  - `PATCH /v1/scenarios/{id}`: Updates scenario draft fields (`ScenarioUpdate`).
  - `DELETE /v1/scenarios/{id}`: Soft/hard deletes a scenario.
  - `POST /v1/scenarios/{id}/publish`: Compiles and publishes scenario using `PublishService`.
  - `POST /v1/scenarios/{id}/playtest`: Clones draft into an isolated playtest copy.
  - `GET /v1/scenarios`: Paginated discovery feed supporting filtering by genre, tags, complexity tier, player count, creator, and bookmarks (`ScenarioListResponse`).
  - `POST /v1/scenarios/{id}/bookmark`: Toggles bookmark state for the calling user.
  - `GET /v1/scenarios/{id}/reviews` / `POST /v1/scenarios/{id}/reviews`: Lists and creates player reviews/ratings (enforcing >= 10 turns played requirement).
  - `GET /v1/scenarios/{id}/playthroughs`: Lists public playthrough summaries for community spectating.
- **Dependencies & Interactions:** Injects `ScenarioService`, `PublishService`, and `PlaythroughService`. Emits background tasks for memory indexing.
- **Architecture Rules & Invariants:** Enforces creator ownership on mutating endpoints. Public discovery allows optional authentication.

### `apps/core-api/app/routers/playthroughs.py`
- **Purpose & Layer:** Playthrough lifecycle and participation controller (`/v1/playthroughs`).
- **Key Endpoints & Exports:**
  - `POST /v1/playthroughs`: Initiates a new playthrough from a published scenario (`PlaythroughCreate`).
  - `GET /v1/playthroughs/{id}`: Fetches active playthrough state, participant sheet, and game mode.
  - `GET /v1/playthroughs`: Lists all playthroughs belonging to the authenticated user.
  - `POST /v1/playthroughs/{id}/join`: Enrolls a multiplayer participant into an active session.
  - `PATCH /v1/playthroughs/{id}/state`: Updates character sheet fields or client-side game state.
  - `POST /v1/playthroughs/{id}/abandon`: Marks a playthrough as abandoned.
- **Dependencies & Interactions:** Injects `PlaythroughService` and `ScenarioService`.
- **Architecture Rules & Invariants:** Verifies participant membership before returning non-public playthrough data.

### `apps/core-api/app/routers/entities.py`
- **Purpose & Layer:** Master Mode entity registry controller (`/v1/scenarios/{scenario_id}/entities`).
- **Key Endpoints & Exports:**
  - `POST /v1/scenarios/{scenario_id}/entities`: Defines an NPC, item, location, or faction entity (`EntityCreate`).
  - `GET /v1/scenarios/{scenario_id}/entities`: Lists all entities configured for a scenario.
  - `GET /v1/scenarios/{scenario_id}/entities/{entity_id}`: Retrieves single entity definition.
  - `PATCH /v1/scenarios/{scenario_id}/entities/{entity_id}`: Updates entity state attributes.
  - `DELETE /v1/scenarios/{scenario_id}/entities/{entity_id}`: Removes entity.
- **Dependencies & Interactions:** Injects `EntityService`. Validates scenario ownership.
- **Architecture Rules & Invariants:** Only accessible to the scenario author when the scenario is in draft status.

### `apps/core-api/app/routers/scenario_entity_types.py`
- **Purpose & Layer:** Entity taxonomy and archetype configuration (`/v1/scenarios/{scenario_id}/entity-types`).
- **Key Endpoints & Exports:**
  - `GET`, `POST`, `PATCH`, `DELETE` on scenario entity types.
  - Allows creators to define custom categorization schemes beyond canonical types.
- **Dependencies & Interactions:** Injects `ScenarioEntityTypeService`.

### `apps/core-api/app/routers/facts.py`
- **Purpose & Layer:** Lore and world knowledge management (`/v1/scenarios/{scenario_id}/facts`).
- **Key Endpoints & Exports:**
  - `POST`, `GET`, `PATCH`, `DELETE` for scenario world facts (`FactCreate`, `FactResponse`).
- **Dependencies & Interactions:** Injects `FactService`. Facts defined here are synchronized to the Memory Service upon publishing.

### `apps/core-api/app/routers/conditions.py`
- **Purpose & Layer:** State condition authoring router (`/v1/scenarios/{scenario_id}/conditions`).
- **Key Endpoints & Exports:**
  - CRUD operations for dynamic state conditions (`ConditionCreate`, `ConditionResponse`).
- **Dependencies & Interactions:** Injects `ConditionService`.

### `apps/core-api/app/routers/end_conditions.py`
- **Purpose & Layer:** Win/loss outcome authoring router (`/v1/scenarios/{scenario_id}/end-conditions`).
- **Key Endpoints & Exports:**
  - CRUD operations for end conditions, trigger rules, and final outcome narration prompts.
- **Dependencies & Interactions:** Injects `EndConditionService`. Validates safe boolean AST expressions.

### `apps/core-api/app/routers/invariants.py`
- **Purpose & Layer:** Rule invariant authoring router (`/v1/scenarios/{scenario_id}/invariants`).
- **Key Endpoints & Exports:**
  - CRUD operations for game rule invariants (bounds, numeric limits, immutable fields).
- **Dependencies & Interactions:** Injects `InvariantService`.

### `apps/core-api/app/routers/maps.py`
- **Purpose & Layer:** Spatial cartography, pins, and connection controller (`/v1/scenarios/{scenario_id}/maps`).
- **Key Endpoints & Exports:**
  - Map management: `POST`, `GET`, `PATCH`, `DELETE` for scenario maps.
  - Pin management: `POST /maps/{map_id}/pins`, `PATCH /pins/{pin_id}`, `DELETE /pins/{pin_id}`.
  - Connection management: `POST /maps/{map_id}/connections`, `DELETE /connections/{connection_id}`.
- **Dependencies & Interactions:** Injects `MapService`.

### `apps/core-api/app/routers/auth.py`
- **Purpose & Layer:** User authentication and identity exchange router (`/v1/auth`).
- **Key Endpoints & Exports:**
  - `POST /v1/auth/sync`: Exchanges Firebase Bearer token for synced local `User` record.
  - `GET /v1/auth/me`: Returns currently authenticated user profile (`UserResponse`).
  - `PATCH /v1/auth/me`: Updates username, bio, and preferences.
- **Dependencies & Interactions:** Injects `AuthService`.
- **Architecture Rules & Invariants:** Validates Firebase JWT before touching user records.

### `apps/core-api/app/routers/users.py`
- **Purpose & Layer:** Public creator profile and statistics router (`/v1/users`).
- **Key Endpoints & Exports:**
  - `GET /v1/users/{user_id}`: Retrieves public creator profile, published scenarios, and achievements.
  - `GET /v1/users/{user_id}/scenarios`: Lists public scenarios by user.
- **Dependencies & Interactions:** Injects `UserService`.

### `apps/core-api/app/routers/share.py`
- **Purpose & Layer:** Social share link token generator and resolver (`/v1/share`).
- **Key Endpoints & Exports:**
  - `POST /v1/share`: Generates signed spectator or multiplayer join share token (`ShareCreate`).
  - `GET /v1/share/{token}`: Resolves share token to playthrough metadata.
- **Dependencies & Interactions:** Injects `ShareService`.

### `apps/core-api/app/routers/uploads.py`
- **Purpose & Layer:** Asset upload management router (`/v1/uploads`).
- **Key Endpoints & Exports:**
  - `POST /v1/uploads/cover-image`: Requests signed Google Cloud Storage upload URL for scenario cover art.
  - `POST /v1/uploads/map-image`: Requests signed upload URL for interactive map graphics.
- **Dependencies & Interactions:** Injects `UploadService` and `StorageClient`.

### `apps/core-api/app/routers/logs.py`
- **Purpose & Layer:** Client-side telemetry and logging ingestion (`/v1/logs`).
- **Key Endpoints & Exports:**
  - `POST /v1/logs`: Receives structured error reports and telemetry from frontend applications.
- **Dependencies & Interactions:** Injects `LogIngestionService`.

### `apps/core-api/app/routers/ratings.py`
- **Purpose & Layer:** Sub-module placeholder for review/rating endpoints, consolidated into `scenarios.py` to maintain RESTful resource hierarchy (`/v1/scenarios/{id}/reviews`).
