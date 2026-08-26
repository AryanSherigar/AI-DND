# Spec: Core API Async Database Connection Layer

## 1. Objective & User Outcome
- **Problem Statement:** The Core API service needs a thread-safe, asynchronous database connection pool and FastAPI session dependency to interact with the PostgreSQL database via SQLAlchemy 2.0 and `asyncpg`. Currently, `apps/core-api/app/db/connection.py` is empty.
- **User Story:** As a Core API service developer, I want a reliable async SQLAlchemy session provider so that services and repositories can execute asynchronous database queries cleanly without leaking connections or blocking the event loop.
- **Success Criteria:**
  - `create_async_engine` initialized using `settings.database_url`, with pool settings read from `config.py` (`settings.db_pool_size`, `settings.db_max_overflow`).
  - `async_sessionmaker` configured with `AsyncSession` and `expire_on_commit=False`.
  - Async generator `get_db_session()` providing an `AsyncSession` for FastAPI dependency injection (`Depends(get_db_session)`), with automatic cleanup and rollback on exception.
  - `close_db_connection()` disposes the engine's connection pool on app shutdown, wired into FastAPI's lifespan handler in `main.py`.
  - Complete compliance with `AGENTS.md` rules (strict type hints, functions under 30 lines, nesting ≤ 2 levels, no untyped signatures).
  - Integration tests, run against a live Postgres instance (see 3.2), verifying connection checkout, transaction rollback, and session cleanup.
  - `settings.database_url`, `settings.db_pool_size`, `settings.db_max_overflow`, and `settings.environment` defined as typed fields on `app.config.settings`.

## 2. Technical Architecture & Data Flow
- **Components Involved:** FastAPI, SQLAlchemy 2.0 (`sqlalchemy.ext.asyncio`), `asyncpg`, Pydantic Settings (`app.config.settings`).
- **Sequence Flow:**
  1. Core API receives an incoming HTTP request requiring database interaction.
  2. Router injects `db: AsyncSession = Depends(get_db_session)`.
  3. `get_db_session()` yields an isolated `AsyncSession` bound to the global `async_engine`.
  4. Repository executes queries using the session.
  5. On completion, `get_db_session()` closes the session. On exception, it executes `await session.rollback()` before raising the error.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Build / Run Dev:** `uvicorn app.main:app --reload`
- **Test:** `pytest tests/db/test_connection.py`
- **Lint / Type-Check:** `ruff check . --fix` and `ruff format .`

### 3.2. Testing Strategy & Conformance
- **Test Directory:** `apps/core-api/tests/db/test_connection.py`.
- **Integration Test Execution:** Tests run against a live Postgres instance — `docker-compose up postgres` (from the repo's `docker-compose.yml`) must be running before `pytest tests/db/` executes. These are integration tests, not unit tests with mocks; there is no in-memory or testcontainer fallback in this spec.
- **Test Cases:**
  - Test session generation via `get_db_session()` yields a usable `AsyncSession`.
  - Test query execution (`SELECT 1`) over the async session, confirming the pool and engine are wired correctly.
  - Test automatic transaction rollback on an exception raised inside the session block.
  - Test `close_db_connection()` disposes the engine without error, and that a session cannot be checked out afterward.

### 3.3. Project Structure & File Layout
- Files created/modified:
  - `apps/core-api/app/config.py` (added `db_pool_size` and `db_max_overflow` settings)
  - `apps/core-api/app/db/connection.py` (implementation using `settings`)
  - `apps/core-api/app/main.py` (wired `close_db_connection()` into lifespan handler)
  - `apps/core-api/tests/db/test_connection.py` (integration test)

### 3.4. Code Style & Interfaces

#### `app/config.py`
```python
class Settings(BaseSettings):
    ...
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aidnd_db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    environment: str = "development"
```

#### `app/db/connection.py`
```python
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Engine and session factory instantiation.
# Pool size/overflow read from app.config.settings.
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for FastAPI dependency injection.

    Usage in a router:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db_session)) -> ...:
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db_connection() -> None:
    """Dispose of the async engine's connection pool.

    Call from the FastAPI lifespan shutdown handler in `main.py`:
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            yield
            await close_db_connection()
    """
    await async_engine.dispose()
```

### 3.5. Git & Review Workflow
- Suggested branch: `feat/core-api-db-connection`
- PR checklist:
  - `ruff format .` & `ruff check .` pass cleanly.
  - All pytest tests in `tests/db/` pass against live Postgres.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Annotate parameters & return types explicitly; handle exception rollback; close sessions cleanly in `finally`.
- ⚠️ **Ask First:** Modifying database models or connection parameters.
- 🚫 **Never:** Use synchronous SQLAlchemy drivers or synchronous `Session`; block the asyncio event loop; read `os.environ` outside `config.py`.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- Database unreachable on startup / during query: `get_db_session` rolls back and closes session before propagating exception.
- Graceful shutdown: `close_db_connection()` disposes the engine pool during FastAPI shutdown event cleanly.

## 5. Phased Implementation Tasks (Task Checklist)
- [x] **Task 1 (Config Update):** Define `db_pool_size: int = 5` and `db_max_overflow: int = 10` in `apps/core-api/app/config.py`.
- [x] **Task 2 (Connection Module):** Implement `apps/core-api/app/db/connection.py` reading settings from `config.py`.
- [x] **Task 3 (Lifespan Integration):** Wire `close_db_connection` into `apps/core-api/app/main.py` lifespan context manager.
- [x] **Task 4 (Integration Tests):** Implement `apps/core-api/tests/db/test_connection.py` to test session creation, `SELECT 1`, rollback on exception, and disposal.
- [x] **Task 5 (Lint & Validation):** Run `ruff check . --fix`, `ruff format .`, and run `pytest tests/db/test_connection.py`.
