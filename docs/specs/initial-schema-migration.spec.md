# Spec: Initial Database Schema Migration (001_initial_schema.py)

## 1. Objective & User Outcome
- **Problem Statement:** The AI-DND platform requires a unified, durable relational schema in PostgreSQL 16 to persist users, scenarios, active conditions, playthroughs, participants, share tokens, and append-only turn logs.
- **User Story:** As an AI-DND system engineer, I want a single, clean, reversible Alembic migration (`001_initial_schema.py`) that sets up all 7 relational tables with precise indexes, default JSONB shapes, check constraints, and foreign key rules, so that Core API and Turn Resolution Service can operate on a consistent database foundation.
- **Success Criteria:**
  - Alembic `upgrade head` succeeds against Postgres and creates all 7 tables (`users`, `scenarios`, `scenario_conditions`, `playthroughs`, `participants`, `playthrough_shares`, `turn_logs`) with expected columns, defaults, check constraints, foreign keys, and indexes.
  - Alembic `downgrade base` cleanly drops all tables and indexes without leaving orphaned types or constraints.
  - `ruff check .` and `ruff format .` pass with zero warnings.

---

## 2. Technical Architecture & Data Flow
- **Components Involved:** Core API (Alembic + SQLAlchemy / asyncpg), PostgreSQL 16.
- **Sequence Flow:**
  1. Developer or CI runner executes `alembic upgrade head`.
  2. Alembic executes `001_initial_schema.py` `upgrade()` function within a transaction.
  3. Table creation order guarantees foreign key dependencies:
     `users` -> `scenarios` -> `scenario_conditions` -> `playthroughs` -> `participants` -> `playthrough_shares` -> `turn_logs`.
  4. Indexes (including PostgreSQL GIN index on `scenarios.genre_tags` and composite index on `turn_logs(playthrough_id, turn_number)`) are created.

---

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- Build: N/A (Python / Alembic migration)
- Migration Apply: `cd apps/core-api && alembic upgrade head`
- Migration Rollback: `cd apps/core-api && alembic downgrade base`
- Test: `cd apps/core-api && pytest tests/test_migrations.py` (or targeted migration integration test)
- Lint / Format: `cd apps/core-api && ruff format . && ruff check . --fix`

### 3.2. Testing Strategy & Conformance
- **Test File Location:** `apps/core-api/tests/db/test_initial_schema_migration.py`
- **Scenarios to Test:**
  1. **Upgrade Execution:** Run `alembic upgrade head` on a test database and verify table existence and column types using SQLAlchemy Inspector.
  2. **Check Constraint Conformance:** Assert that invalid enum strings (e.g. `mode='invalid'`) raise SQL Check Constraint violations.
  3. **Foreign Key Deletion Rules:** Verify deleting a `Scenario` cascades to `scenario_conditions` but raises `RESTRICT` error if referenced by an active `Playthrough`.
  4. **GIN Index Verification:** Execute a `@>` array overlap query against `scenarios.genre_tags` to verify query plan index usage.
  5. **Downgrade Execution:** Run `alembic downgrade base` and verify all tables are completely dropped.

### 3.3. Project Structure & File Layout
- **Files to create/overwrite:**
  - `apps/core-api/app/db/migrations/versions/001_initial_schema.py`
  - `docs/specs/initial-schema-migration.spec.md` (this file)
  - `apps/core-api/tests/db/test_initial_schema_migration.py`
- **Files to delete (if any exist):**
  - Any superseded split migration versions (e.g. `002_scenario_additions.py`, `003_scenario_condition.py`)

### 3.4. Code Style & Interfaces
- **Alembic Revision Header:**
  ```python
  """initial schema

  Revision ID: 001_initial_schema
  Revises:
  Create Date: 2026-08-27
  """

  from alembic import op
  import sqlalchemy as sa
  from sqlalchemy.dialects import postgresql

  revision = "001_initial_schema"
  down_revision = None
  branch_labels = None
  depends_on = None
  ```

- **Table Definitions Summary:**
  1. `users`:
     - `user_id`: UUID, Primary Key, `server_default=sa.text("gen_random_uuid()")`
     - `display_name`: VARCHAR(255), `nullable=False`
     - `auth_provider_id`: VARCHAR(255), `nullable=False`, `unique=True`, `index=True`
     - `created_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`

  2. `scenarios`:
     - `scenario_id`: UUID, Primary Key, `server_default=sa.text("gen_random_uuid()")`
     - `creator_id`: UUID, FK -> `users.user_id` (`ondelete="RESTRICT"`), `nullable=False`
     - `title`: VARCHAR(255), `nullable=False`
     - `mode`: VARCHAR(20), Check `mode IN ('newbie', 'master')`, `nullable=False`
     - `world_data`: JSONB, `nullable=False`, `server_default=sa.text("'{}'::jsonb")`
     - `status`: VARCHAR(20), Check `status IN ('draft', 'published')`, `nullable=False`, `server_default='draft'`
     - `genre_tags`: `postgresql.ARRAY(sa.Text())`, `nullable=False`, `server_default=sa.text("'{}'::text[]")`
     - `complexity_tier`: VARCHAR(20), Check `complexity_tier IN ('newbie', 'intermediate', 'master')`, `nullable=False`
     - `player_count_support`: VARCHAR(20), Check `player_count_support IN ('solo', 'multiplayer', 'both')`, `nullable=False`
     - `estimated_playtime`: VARCHAR(50), `nullable=True`
     - `cover_image_url`: VARCHAR(1024), `nullable=True`
     - `content_tag`: VARCHAR(100), `nullable=True`
     - `play_count`: INTEGER, `nullable=False`, `server_default="0"`
     - `rating_avg`: NUMERIC(3, 2), `nullable=False`, `server_default="0.00"`
     - `narrator_persona`: TEXT, `nullable=True`
     - `setup_schema`: JSONB, `nullable=False`, `server_default=sa.text("'[]'::jsonb")`
     - `state_schema`: JSONB, `nullable=False`, `server_default=sa.text("'{}'::jsonb")`
     - `end_conditions`: JSONB, `nullable=False`, `server_default=sa.text("'[]'::jsonb")`
     - `checkpoints`: JSONB, `nullable=False`, `server_default=sa.text("'[]'::jsonb")`
     - `rules`: JSONB, `nullable=False`, `server_default=sa.text("'{}'::jsonb")`
     - `current_version`: INTEGER, `nullable=False`, `server_default="1"`
     - `created_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`
     - `updated_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`
     - *Index:* `idx_scenarios_genre_tags` GIN on `genre_tags`

  3. `scenario_conditions`:
     - `condition_id`: UUID, Primary Key, `server_default=sa.text("gen_random_uuid()")`
     - `scenario_id`: UUID, FK -> `scenarios.scenario_id` (`ondelete="CASCADE"`), `nullable=False`
     - `label`: VARCHAR(255), `nullable=False`
     - `condition_expression`: JSONB, `nullable=False`, `server_default=sa.text("'{}'::jsonb")`
     - `condition_version`: VARCHAR(50), `nullable=False`, `server_default="'1.0'"`
     - `narrator_instruction`: TEXT, `nullable=False`
     - `metadata`: JSONB, `nullable=False`, `server_default=sa.text("'{}'::jsonb")`
     - `created_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`

  4. `playthroughs`:
     - `playthrough_id`: UUID, Primary Key, `server_default=sa.text("gen_random_uuid()")`
     - `scenario_id`: UUID, FK -> `scenarios.scenario_id` (`ondelete="RESTRICT"`), `nullable=False`
     - `created_by`: UUID, FK -> `users.user_id` (`ondelete="RESTRICT"`), `nullable=False`
     - `state`: JSONB, `nullable=False`, `server_default=sa.text("'{}'::jsonb")`
     - `checkpoint`: VARCHAR(255), `nullable=True`
     - `turn_count`: INTEGER, `nullable=False`, `server_default="0"`
     - `status`: VARCHAR(20), Check `status IN ('active', 'completed', 'abandoned')`, `nullable=False`, `server_default='active'`
     - `scenario_version`: INTEGER, `nullable=False`
     - `scenario_snapshot`: JSONB, `nullable=False`, `server_default=sa.text("'{}'::jsonb")`
     - `created_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`
     - `updated_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`

  5. `participants`:
     - `participant_id`: UUID, Primary Key, `server_default=sa.text("gen_random_uuid()")`
     - `playthrough_id`: UUID, FK -> `playthroughs.playthrough_id` (`ondelete="RESTRICT"`), `nullable=False`
     - `user_id`: UUID, FK -> `users.user_id` (`ondelete="RESTRICT"`), `nullable=False`
     - `role`: VARCHAR(20), Check `role IN ('owner', 'joined')`, `nullable=False`
     - `turn_order_position`: INTEGER, `nullable=False`
     - `joined_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`

  6. `playthrough_shares`:
     - `share_id`: UUID, Primary Key, `server_default=sa.text("gen_random_uuid()")`
     - `share_token`: VARCHAR(255), `nullable=False`, `unique=True`, `index=True`
     - `playthrough_id`: UUID, FK -> `playthroughs.playthrough_id` (`ondelete="RESTRICT"`), `nullable=False`
     - `mode`: VARCHAR(20), Check `mode IN ('spectate', 'join')`, `nullable=False`
     - `created_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`

  7. `turn_logs`:
     - `turn_id`: UUID, Primary Key, `server_default=sa.text("gen_random_uuid()")`
     - `playthrough_id`: UUID, FK -> `playthroughs.playthrough_id` (`ondelete="RESTRICT"`), `nullable=False`
     - `turn_number`: INTEGER, `nullable=False`
     - `participant_id`: UUID, FK -> `participants.participant_id` (`ondelete="RESTRICT"`), `nullable=True`
     - `action_text`: TEXT, `nullable=False`
     - `narration_text`: TEXT, `nullable=True`
     - `tool_calls`: JSONB, `nullable=False`, `server_default=sa.text("'[]'::jsonb")`
     - `created_at`: TIMESTAMP WITH TIME ZONE, `nullable=False`, `server_default=sa.text("CURRENT_TIMESTAMP")`
     - *Index:* `idx_turn_logs_playthrough_turn` Composite Index on `(playthrough_id, turn_number)`

### 3.5. Git & Review Workflow
- Branch name: `feat/initial-schema-migration`
- Commit message: `feat(core-api): implement 001_initial_schema database migration`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Ensure `downgrade()` perfectly unwinds all creations in reverse topological order; run `ruff format .` and `ruff check .` before completion.
- ⚠️ **Ask First:** Modifying schema definitions after migration has been executed in a shared DB environment.
- 🚫 **Never:** Use raw string interpolation for SQL/table names; hardcode DB credentials in migration scripts.

---

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **PostgreSQL Extension Dependency:** `gen_random_uuid()` is built-in for PostgreSQL 13+. For PostgreSQL 16 (our stack), no `uuid-ossp` extension is required.
- **Rollback Safety:** Table removal order in `downgrade()` must strictly be `turn_logs` -> `playthrough_shares` -> `participants` -> `playthroughs` -> `scenario_conditions` -> `scenarios` -> `users` to avoid foreign key dependency errors.

---

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Migration Script):** Write complete `001_initial_schema.py` migration file with all 7 tables, check constraints, default JSONB values, and indexes.
- [ ] **Task 2 (Code Formatting & Validation):** Run `ruff format` and `ruff check --fix` on `001_initial_schema.py`.
- [ ] **Task 3 (Verification / Test):** Verify migration syntax and run migration downgrade/upgrade cycle against test database.
