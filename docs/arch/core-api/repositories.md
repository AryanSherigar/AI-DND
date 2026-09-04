# Core API Architecture — Repositories & Data Access

This document details all 14 repository classes located in `apps/core-api/app/repositories/`. Repositories represent the sole layer authorized to execute SQL, interact with SQLAlchemy models, and issue database queries.

---

## 1. Overview & Data Access Invariants

In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md):
- **SQL resides exclusively in repositories.** No queries, ORM expressions, or `select()` statements exist in routers or services.
- **One repository per entity domain.**
- **No logging in repositories.** Repositories are dumb data-access objects; logging is handled at the service layer.
- **AsyncPG Execution**: All operations run asynchronously using `await session.execute(...)` and `await session.flush()`.
- **N+1 Query Prevention**: Cross-table loads use joins or `selectinload` where appropriate.

---

## 2. Repository File Profiles

### `apps/core-api/app/repositories/scenario_repo.py`
- **Purpose & Layer:** Persistence and query repository for the core `Scenario` entity.
- **Key Methods & SQL Patterns:**
  - `create(scenario)`: Inserts new scenario instance and flushes.
  - `get_by_id(scenario_id)`: Fetches single scenario by UUID primary key.
  - `update(scenario)`: Flushes and refreshes dirty attributes.
  - `delete(scenario)`: Deletes scenario row.
  - `count_playthroughs(scenario_id)`: Issues `SELECT count() FROM playthroughs WHERE scenario_id = :id`.
  - `list_scenarios(...)`: Builds dynamic query supporting filtering by `creator_id`, `published_only`, `genre_tags` (Postgres array overlap), `complexity_tier`, `player_count_support`, and sorting by `created_at`, `play_count`, or `rating_score`. Implements offset/limit pagination.
  - `get_bookmark(user_id, scenario_id)` / `add_bookmark(...)` / `delete_bookmark(...)`: Manages bookmark joins.
  - `list_reviews(...)` / `add_review(...)`: Manages `ScenarioReview` rows.
- **Dependencies & Interactions:** Consumed by `ScenarioService`, `PublishService`, and `RatingService`.

### `apps/core-api/app/repositories/playthrough_repo.py`
- **Purpose & Layer:** Data access for active and completed game sessions (`Playthrough`).
- **Key Methods & SQL Patterns:**
  - `create(playthrough)`: Persists new playthrough record.
  - `get_by_id(playthrough_id)`: Loads playthrough with joined scenario metadata.
  - `list_by_user(user_id, status)`: Queries playthroughs where the user is an active participant.
  - `update_state(playthrough_id, state_patch)`: Updates JSONB `current_state` blob.
- **Dependencies & Interactions:** Consumed by `PlaythroughService`.

### `apps/core-api/app/repositories/participant_repo.py`
- **Purpose & Layer:** Data access for player enrollment and character sheets (`Participant`).
- **Key Methods & SQL Patterns:**
  - `add_participant(...)`, `get_by_playthrough_and_user(...)`, `update_character_data(...)`.
- **Dependencies & Interactions:** Consumed by `PlaythroughService`.

### `apps/core-api/app/repositories/entity_repo.py`
- **Purpose & Layer:** Persistence for Master Mode scenario entities (`Entity`).
- **Key Methods & SQL Patterns:**
  - CRUD queries scoped to `scenario_id`.
  - `list_by_scenario(scenario_id)`: Retrieves all NPCs, items, locations, and factions for a scenario.
- **Dependencies & Interactions:** Consumed by `EntityService` and `PublishService`.

### `apps/core-api/app/repositories/scenario_entity_type_repo.py`
- **Purpose & Layer:** Data access for custom entity archetype taxonomies.
- **Key Methods & SQL Patterns:** Scoped queries by `scenario_id` for custom entity schema definitions.
- **Dependencies & Interactions:** Consumed by `ScenarioEntityTypeService`.

### `apps/core-api/app/repositories/fact_repo.py`
- **Purpose & Layer:** Persistence for scenario world lore facts (`Fact`).
- **Key Methods & SQL Patterns:**
  - `list_by_scenario(scenario_id)`: Loads all subject-predicate-object knowledge rows.
- **Dependencies & Interactions:** Consumed by `FactService` and `PublishService`.

### `apps/core-api/app/repositories/condition_repo.py`
- **Purpose & Layer:** Data access for dynamic scenario conditions (`ScenarioCondition`).
- **Key Methods & SQL Patterns:** Queries condition trigger expressions by `scenario_id`.
- **Dependencies & Interactions:** Consumed by `ConditionService`.

### `apps/core-api/app/repositories/end_condition_repo.py`
- **Purpose & Layer:** Persistence for win/loss conditions (`EndCondition`).
- **Key Methods & SQL Patterns:** Scoped queries for terminal condition rules and outcome messages.
- **Dependencies & Interactions:** Consumed by `EndConditionService`.

### `apps/core-api/app/repositories/invariant_repo.py`
- **Purpose & Layer:** Data access for rule boundary invariants (`RuleInvariant`).
- **Key Methods & SQL Patterns:** Queries expression trees that constrain game state values.
- **Dependencies & Interactions:** Consumed by `InvariantService`.

### `apps/core-api/app/repositories/map_repo.py`
- **Purpose & Layer:** Complex spatial data access for scenario maps, pins, and graph connections.
- **Key Methods & SQL Patterns:**
  - Maps: CRUD operations for `ScenarioMap` rows.
  - Pins: CRUD for `MapPin` coordinates and linked entity identifiers.
  - Connections: CRUD for bidirectional `MapConnection` edges connecting pins.
- **Dependencies & Interactions:** Consumed by `MapService` and `PublishService`.

### `apps/core-api/app/repositories/rating_repo.py`
- **Purpose & Layer:** Aggregate rating computations and review scoring queries.
- **Key Methods & SQL Patterns:** Executes SQL `AVG()` and `COUNT()` aggregations over scenario review records.
- **Dependencies & Interactions:** Consumed by `RatingService` and `ScenarioService`.

### `apps/core-api/app/repositories/share_repo.py`
- **Purpose & Layer:** Persistence and resolution of cryptographically generated share tokens (`Share`).
- **Key Methods & SQL Patterns:**
  - `create_share(share)`: Persists token, target playthrough, role (spectator/participant), and expiry.
  - `get_by_token(token)`: Looks up valid, unexpired share records.
- **Dependencies & Interactions:** Consumed by `ShareService`.

### `apps/core-api/app/repositories/turn_log_repo.py`
- **Purpose & Layer:** Read-only data access for historical gameplay turns (`TurnLog`).
- **Key Methods & SQL Patterns:**
  - Queries historical narration, user actions, tool calls, and state transitions ordered by `turn_number ASC`.
- **Dependencies & Interactions:** Consumed by `PlaythroughService`.

### `apps/core-api/app/repositories/user_repo.py`
- **Purpose & Layer:** User identity, profile data, and author statistics data access (`User`).
- **Key Methods & SQL Patterns:**
  - `get_by_id(user_id)`, `get_by_firebase_uid(uid)`, `create(user)`, `update(user)`.
- **Dependencies & Interactions:** Consumed by `AuthService` and `UserService`.
