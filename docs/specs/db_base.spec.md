# Spec: Core API Database Base & ORM Layer Foundation

## 1. Objective & User Outcome
- **Problem Statement:** The `apps/core-api` service currently lacks a centralized SQLAlchemy 2.0 `DeclarativeBase` setup, naming conventions, reusable ORM mixins, domain ORM models, and Alembic metadata integration. Without this foundation, repositories cannot interact with PostgreSQL using typed ORM entities, and Alembic migrations cannot autogenerate or validate metadata schemas cleanly.
- **User Story:** As a backend developer, I want a robust SQLAlchemy 2.0 `Base` with explicit constraint naming conventions, reusable UUID/timestamp mixins, domain ORM models matching our initial database schema, and Alembic `target_metadata` wiring in `env.py`, so that all database access in `apps/core-api` is type-safe, consistent, and strictly layered.
- **Success Criteria:**
  - `apps/core-api/app/db/base.py` exports `Base`, `NAMING_CONVENTION`, `TimestampMixin`, `UUIDPrimaryKeyMixin`, and re-exports all ORM model classes (`User`, `Scenario`, `ScenarioCondition`, `Playthrough`, `Participant`, `PlaythroughShare`, `TurnLog`).
  - `apps/core-api/app/db/models/` contains ORM declarations matching the initial schema migration (`001_initial_schema.py`).
  - `apps/core-api/app/db/migrations/env.py` imports `Base` from `app.db.base` and sets `target_metadata = Base.metadata`.
  - Code formatting and linting pass (`ruff format .` and `ruff check . --fix`) with zero warnings.
  - Automated test suite in `tests/db/test_base.py` passes.

---

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - `apps/core-api/app/db/base.py`: Central DeclarativeBase definition with explicit constraint naming convention and mixins.
  - `apps/core-api/app/db/models/`: ORM model package (`__init__.py`, `user.py`, `scenario.py`, `scenario_condition.py`, `playthrough.py`, `participant.py`, `share.py`, `turn_log.py`).
  - `apps/core-api/app/db/migrations/env.py`: Alembic environment configuration script set to `target_metadata = Base.metadata`.
- **Sequence Flow:**
  - **Runtime Data Access:** Repository methods import ORM models from `app.db.models` (or `app.db.base`) and execute async SQLAlchemy queries via `AsyncSession`.
  - **Migration Management:** Alembic execution loads `apps/core-api/app/db/migrations/env.py`, which imports `Base` from `app.db.base`, inspects `Base.metadata`, and compares registered ORM models against PostgreSQL database tables.

---

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Build / Compile Check:** `cd apps/core-api && python -m py_compile app/db/base.py`
- **Test:** `cd apps/core-api && pytest tests/db/test_base.py`
- **Lint / Type-Check:** `cd apps/core-api && ruff check app/db/ && ruff format --check app/db/`

---

### 3.2. Testing Strategy & Conformance
- **Test File Location:** `apps/core-api/tests/db/test_base.py`
- **Test Cases:**
  1. `test_base_metadata_contains_all_tables`: Verify `Base.metadata.tables.keys()` contains `users`, `scenarios`, `scenario_conditions`, `playthroughs`, `participants`, `playthrough_shares`, and `turn_logs`.
  2. `test_naming_convention_configuration`: Verify `Base.metadata.naming_convention` matches specified index, unique, check, foreign key, and primary key templates.
  3. `test_orm_models_column_definitions`: Verify primary key UUID generation, foreign keys, nullable flags, JSONB defaults, and timezone annotations across ORM models.

---

### 3.3. Project Structure & File Layout
- **Files to Create:**
  - `docs/specs/db_base.spec.md`
  - `apps/core-api/app/db/models/__init__.py`
  - `apps/core-api/app/db/models/user.py`
  - `apps/core-api/app/db/models/scenario.py`
  - `apps/core-api/app/db/models/scenario_condition.py`
  - `apps/core-api/app/db/models/playthrough.py`
  - `apps/core-api/app/db/models/participant.py`
  - `apps/core-api/app/db/models/share.py`
  - `apps/core-api/app/db/models/turn_log.py`
  - `apps/core-api/tests/db/test_base.py`
- **Files to Modify:**
  - `apps/core-api/app/db/base.py`
  - `apps/core-api/app/db/migrations/env.py`

---

### 3.4. Code Style & Interfaces
- **SQLAlchemy 2.0 Mapping Style:** Use `Mapped[T]` type annotations and `mapped_column(...)`.
- **Type Annotations:** Explicit Python 3.10+ union syntax (`T | None`). No `Any` types.
- **Naming Convention Contract:**
  ```python
  NAMING_CONVENTION = {
      "ix": "ix_%(column_0_label)s",
      "uq": "uq_%(table_name)s_%(column_0_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }
  ```
- **DeclarativeBase Structure:**
  ```python
  from sqlalchemy import MetaData
  from sqlalchemy.orm import DeclarativeBase


  class Base(DeclarativeBase):
      metadata = MetaData(naming_convention=NAMING_CONVENTION)
  ```

---

### 3.5. Git & Review Workflow
- **Branch:** `feat/core-api-db-base-models`
- **PR Review Checklist:**
  - Zero ruff warnings (`ruff check .` & `ruff format .`).
  - No nesting depth > 2 levels; functions under 30 lines.
  - All 7 ORM models registered on `Base.metadata`.
  - `env.py` wired to `Base.metadata`.

---

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use SQLAlchemy 2.0 `Mapped` and `mapped_column`; define explicit constraint naming convention on `MetaData`; log exceptions cleanly.
- ⚠️ **Ask First:** Modifying schema definitions in existing Alembic migration files (`001_initial_schema.py`).
- 🚫 **Never:** Use raw SQL strings in services or routers; use synchronous DB drivers in async context; leave untyped ORM models.

---

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **JSONB Column Defaulting:** Server-side and client-side defaults for JSONB columns must use `'{}'::jsonb` or `'[]'::jsonb` to prevent `None` insertion errors.
- **Timezone Awareness:** All timestamp columns must use `TIMESTAMP(timezone=True)` / `datetime.timezone.utc` to avoid naive datetime bugs.
- **Cascade Deletes vs Restrict:** Foreign key `ondelete` attributes must match `001_initial_schema.py` (`RESTRICT` for critical parent entities, `CASCADE` for scenario conditions).

---

## 5. Phased Implementation Tasks (Task Checklist)

- [x] **Task 1 (DeclarativeBase & Mixins):** Implement `apps/core-api/app/db/base.py` with `NAMING_CONVENTION`, `Base`, `UUIDPrimaryKeyMixin`, and `TimestampMixin`.
- [x] **Task 2 (ORM Models):** Create ORM model classes in `apps/core-api/app/db/models/` for `User`, `Scenario`, `ScenarioCondition`, `Playthrough`, `Participant`, `PlaythroughShare`, and `TurnLog`. Import and re-export them in `apps/core-api/app/db/base.py`.
- [x] **Task 3 (Alembic env.py Wiring):** Wire `apps/core-api/app/db/migrations/env.py` to import `Base` from `app.db.base` and set `target_metadata = Base.metadata`.
- [x] **Task 4 (Tests & Formatting):** Create `apps/core-api/tests/db/test_base.py`, execute pytest suite, and run `ruff format .` and `ruff check . --fix`.
