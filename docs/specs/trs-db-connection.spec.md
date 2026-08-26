# Spec: Turn Resolution Service Async Database Connection Layer

## 1. Objective & User Outcome
- **Problem Statement:** The Turn Resolution Service (TRS) needs a thread-safe, asynchronous database connection pool and FastAPI session dependency to access the PostgreSQL database (`aidnd_db`) for fetching playthrough states, scenario snapshots, participant records, and writing turn logs. Currently, `apps/turn-resolution-service/app/db/connection.py` and `apps/turn-resolution-service/app/config.py` are empty.
- **User Story:** As a Turn Resolution Service developer, I want a reliable async SQLAlchemy session provider so that TRS pipeline steps and repositories can execute asynchronous database queries cleanly without blocking the event loop or leaking connections during SSE narrative generation loops.
- **Success Criteria:**
  - `apps/turn-resolution-service/app/config.py` defined with a Pydantic `Settings` class holding `database_url`, `db_pool_size`, `db_max_overflow`, `secret_key`, and `environment`.
  - `create_async_engine` initialized using `settings.database_url`, with pool settings read from `settings.db_pool_size` and `settings.db_max_overflow`.
  - `AsyncSessionFactory` configured with `AsyncSession` and `expire_on_commit=False`.
  - Async generator `get_db_session()` providing an `AsyncSession` for FastAPI dependency injection (`Depends(get_db_session)`), with automatic cleanup and rollback on exception.
  - `close_db_connection()` disposes the engine's connection pool on app shutdown, wired into FastAPI's lifespan handler in `apps/turn-resolution-service/app/main.py`.
  - Integration tests in `apps/turn-resolution-service/tests/db/test_connection.py` verifying connection checkout, basic query execution, transaction rollback on failure, and engine disposal.
  - Complete compliance with `AGENTS.md` rules (strict type hints, functions under 30 lines, nesting ≤ 2 levels, no untyped signatures).

## 2. Technical Architecture & Data Flow
- **Components Involved:** FastAPI, SQLAlchemy 2.0 (`sqlalchemy.ext.asyncio`), `asyncpg`, Pydantic Settings (`app.config.settings`).
- **Sequence Flow:**
  1. Turn Resolution Service receives an incoming turn action or session request.
  2. Router or pipeline handler injects `db: AsyncSession = Depends(get_db_session)`.
  3. `get_db_session()` yields an isolated `AsyncSession` bound to the service's global `async_engine`.
  4. Repositories read playthrough state or append turn logs using the session.
  5. On completion, `get_db_session()` closes the session. On exception, it executes `await session.rollback()` before re-raising the error.
  6. On FastAPI application shutdown, lifespan context manager calls `close_db_connection()` to dispose of the connection pool.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Build / Run Dev:** `uvicorn app.main:app --reload --port 8001`
- **Test:** `pytest tests/db/test_connection.py`
- **Lint / Type-Check:** `ruff check . --fix` and `ruff format .`

### 3.2. Testing Strategy & Conformance
- **Test Directory:** `apps/turn-resolution-service/tests/db/test_connection.py`.
- **Integration Test Execution:** Tests run against a live Postgres instance (via `docker-compose up postgres` or local PostgreSQL instance running `aidnd_db`).
- **Test Cases:**
  - Test session generation via `get_db_session()` yields a usable `AsyncSession`.
  - Test query execution (`SELECT 1`) over the async session, confirming the pool and engine are wired correctly.
  - Test automatic transaction rollback on an exception raised inside the session block.
  - Test `close_db_connection()` disposes the engine without error.

### 3.3. Project Structure & File Layout
- Files created/modified:
  - `apps/turn-resolution-service/app/config.py` (Pydantic `Settings` definition)
  - `apps/turn-resolution-service/app/db/connection.py` (implementation using `settings`)
  - `apps/turn-resolution-service/app/main.py` (FastAPI app + lifespan context manager)
  - `apps/turn-resolution-service/tests/db/test_connection.py` (integration test)

### 3.4. Code Style & Interfaces

#### `apps/turn-resolution-service/app/config.py`
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TRS application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/aidnd_db"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10
    secret_key: str = "default-secret-key-change-in-production"
    environment: str = "development"


settings = Settings()
```

#### `apps/turn-resolution-service/app/db/connection.py`
```python
"""Database connection and async session management module for TRS."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

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
        @router.post("/turn")
        async def turn(db: AsyncSession = Depends(get_db_session)) -> ...:
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
- Suggested branch: `feat/trs-db-connection`
- PR checklist:
  - `ruff format .` & `ruff check .` pass cleanly with zero warnings.
  - Integration tests in `tests/db/test_connection.py` pass against Postgres.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Annotate parameters & return types explicitly; handle exception rollback; close sessions cleanly in `finally`.
- ⚠️ **Ask First:** Modifying database models or connection parameters.
- 🚫 **Never:** Use synchronous SQLAlchemy drivers or synchronous `Session`; block the asyncio event loop; read `os.environ` outside `config.py`.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- Database unreachable on startup / during query: `get_db_session` rolls back and closes session before propagating exception.
- Graceful shutdown: `close_db_connection()` disposes the engine pool during FastAPI shutdown event cleanly without dangling sockets.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Config Setup):** Implement `apps/turn-resolution-service/app/config.py` with Pydantic `Settings`.
- [ ] **Task 2 (Connection Module):** Implement `apps/turn-resolution-service/app/db/connection.py` with `async_engine`, `AsyncSessionFactory`, `get_db_session`, and `close_db_connection`.
- [ ] **Task 3 (Lifespan Integration):** Implement `apps/turn-resolution-service/app/main.py` with FastAPI lifespan context manager wiring `close_db_connection`.
- [ ] **Task 4 (Integration Tests):** Implement `apps/turn-resolution-service/tests/db/test_connection.py` to test session creation, `SELECT 1`, rollback on error, and pool disposal.
- [ ] **Task 5 (Verification & Linting):** Run `ruff check . --fix`, `ruff format .`, and `pytest tests/db/test_connection.py`.
