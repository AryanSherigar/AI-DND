# Core API Architecture — Database, Models & Migrations

This document details the relational persistence layer in `apps/core-api/app/db/`, covering connection pool management, the declarative ORM base, all SQLAlchemy model entities, and the Alembic migration history (001–007).

---

## 1. Engine & Session Lifecycle (`app/db/connection.py`)

- **Purpose & Layer:** Async database engine configuration and session provider.
- **Key Exports & Symbols:**
  - `async_engine`: Async SQLAlchemy engine created via `create_async_engine(settings.database_url, pool_size=5, max_overflow=10)`.
  - `AsyncSessionFactory`: Configured `async_sessionmaker(bind=async_engine, expire_on_commit=False)`.
  - `get_db_session() -> AsyncGenerator[AsyncSession, None]`: FastAPI dependency yielding an async session. Uses `scope="function"` to force session commit before returning the HTTP response, eliminating eventual-consistency read-after-write races.
  - `get_session_factory() -> async_sessionmaker[AsyncSession]`: Factory for background tasks (e.g. `PublishService.run_publish_job`) that execute outside the request lifecycle.
  - `close_db_connection()`: Engine disposal called during FastAPI lifespan shutdown.
- **Architecture Rules & Invariants:** Zero synchronous database drivers; connection pooling is tuned explicitly via environment settings.

---

## 2. Declarative Base & Mixins (`app/db/base.py`)

- **Purpose & Layer:** ORM base configuration and schema naming conventions.
- **Key Exports & Symbols:**
  - `NAMING_CONVENTION`: Explicit PostgreSQL constraint naming convention (`ix_`, `uq_`, `ck_`, `fk_`, `pk_`), ensuring predictable constraint names across Alembic migrations.
  - `Base(DeclarativeBase)`: Root declarative class.
  - `CreatedAtMixin`: Mixin provisioning timezone-aware `created_at` timestamp defaulting to `CURRENT_TIMESTAMP`.
  - `TimestampMixin(CreatedAtMixin)`: Extends `CreatedAtMixin` with auto-updating `updated_at` column.

---

## 3. SQLAlchemy ORM Entities (`app/db/models/`)

All models reside under `apps/core-api/app/db/models/` and export through `__init__.py`:

### Core Entities
- **`user.py` (`User`)**: Primary account identity. Stores `user_id` (UUID PK), `firebase_uid` (indexed unique string), `email`, `display_name`, `avatar_url`, `bio`, `preferred_genres` (JSONB/array), and timestamps.
- **`scenario.py` (`Scenario`)**: Core game definition. Stores `scenario_id` (UUID PK), `creator_id` (FK -> `User`), `title`, `description`, `logline`, `system_prompt`, `opening_scene`, `genre_tags` (array), `content_tag` (`all-ages`, `teen`, `mature`), `complexity_tier` (`newbie`, `master`), `player_count_support` (`solo`, `duo`, `party`), `state_schema` (JSONB), `is_published` (bool), `status` (`draft`, `publishing`, `published`, `archived`), `play_count` (int), `rating_score` (decimal).
- **`playthrough.py` (`Playthrough`)**: Playthrough instance. Stores `playthrough_id` (UUID PK), `scenario_id` (FK -> `Scenario`), `game_mode`, `current_state` (JSONB dynamic game state), `current_turn` (int), `status` (`active`, `ended`, `abandoned`), `end_outcome` (JSONB), and timestamps.
- **`participant.py` (`Participant`)**: Player character sheet link. Stores `participant_id`, `playthrough_id` (FK), `user_id` (FK), `character_name`, `character_state` (JSONB inventory/stats), `turn_order` (int), `is_active` (bool).
- **`turn_log.py` (`TurnLog`)**: Immutable historical turn journal. Stores `turn_log_id`, `playthrough_id` (FK), `turn_number` (int), `user_action` (text), `narration` (text), `tool_calls` (JSONB array), `state_delta` (JSONB), `timestamp`.

### Master Mode Entities & Lore
- **`entity.py` (`Entity`)**: Master Mode actors and items. Stores `entity_id`, `scenario_id` (FK), `name`, `entity_type` (NPC, Item, Location, Faction), `archetype`, `attributes` (JSONB), `is_dynamic` (bool).
- **`scenario_entity_type.py` (`ScenarioEntityType`)**: Author-defined custom entity archetype taxonomies and attribute validation rules.
- **`fact.py` (`Fact`)**: Triplet lore facts. Stores `fact_id`, `scenario_id` (FK), `subject`, `predicate`, `object_value`, and `category`.
- **`scenario_condition.py` (`ScenarioCondition`)**: State transition triggers. Stores `condition_id`, `scenario_id` (FK), `trigger_expression` (JSONB AST), and `effect_description`.
- **`end_condition.py` (`EndCondition`)**: Game termination criteria. Stores `end_condition_id`, `scenario_id` (FK), `trigger_expression` (JSONB AST), `outcome_type` (`victory`, `defeat`, `neutral`), and `terminal_prompt` (text).
- **`rule_invariant.py` (`RuleInvariant`)**: Gameplay constraint rules. Stores `invariant_id`, `scenario_id` (FK), `expression` (JSONB AST), and `error_message`.

### Cartography & Social
- **`scenario_map.py` (`ScenarioMap`)**: Interactive spatial map canvas. Stores `map_id`, `scenario_id` (FK), `title`, `image_url`, `width`, `height`, and `fog_of_war_enabled`.
- **`map_pin.py` (`MapPin`)**: Coordinates on a map. Stores `pin_id`, `map_id` (FK), `entity_id` (FK optional), `x_percent`, `y_percent`, `label`, `is_discovered`.
- **`map_connection.py` (`MapConnection`)**: Edges connecting map pins. Stores `connection_id`, `map_id` (FK), `source_pin_id` (FK), `target_pin_id` (FK), `is_bidirectional`, and `path_type`.
- **`bookmark.py` (`Bookmark`)**: User saved scenarios. Stores `user_id` (FK) and `scenario_id` (FK) as composite PK.
- **`review.py` (`ScenarioReview`)**: Ratings and textual feedback. Stores `review_id`, `scenario_id` (FK), `user_id` (FK), `rating` (1-5 int), `comment`, and `turns_played`.
- **`share.py` (`Share`)**: Ephemeral or persistent spectator/join links. Stores `share_id`, `token` (indexed unique string), `playthrough_id` (FK), `role` (`spectator`, `participant`), and `expires_at`.

---

## 4. Alembic Migration History (001–007)

Alembic migrations reside in `apps/core-api/app/db/migrations/versions/`:

1. **`001_initial_schema.py`**: Initializes baseline tables (`users`, `scenarios`, `playthroughs`, `participants`, `turn_logs`). Establishes foreign keys, timestamp triggers, and PostgreSQL UUID extensions.
2. **`002_bookmarks_and_reviews.py`**: Adds social interactions. Creates `bookmarks` (composite PK `user_id` + `scenario_id`) and `scenario_reviews` with integer rating constraints (1–5) and review text.
3. **`003_master_mode_entities_facts.py`**: Introduces Master Mode foundations: `entities`, `facts`, `scenario_conditions`, `end_conditions`, and `rule_invariants`.
4. **`004_playthrough_end_outcome.py`**: Adds structured outcome persistence (`end_outcome` JSONB) and game termination timestamps to `playthroughs`.
5. **`005_user_profile_fields.py`**: Expands user profiles with bio, avatar customization, preferred genres, and social links.
6. **`006_scenario_entity_types.py`**: Creates `scenario_entity_types` table for author-defined custom archetype classifications.
7. **`007_master_mode_maps.py`**: Creates spatial cartography tables: `scenario_maps`, `map_pins`, and `map_connections`.
