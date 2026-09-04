"""Database connection and async session management module."""

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

    Always inject with `scope="function"`: FastAPI's default scope for a
    yield-dependency is "request", which defers this function's post-yield
    code (the commit below) until *after* the response has already been sent
    to the client — a real, reproducible race where a client can GET a list
    immediately after a 201 POST and not see the row it just created, because
    the transaction hasn't committed yet. `scope="function"` runs the commit
    before the response is sent, closing that window.

    Usage in a router:
        @router.get("/example")
        async def example(
            db: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
        ) -> ...:
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Provide the session factory for code that needs its own DB session.

    Used by background work (e.g. the publish job) that outlives the
    request-scoped session from `get_db_session`. Overridable in tests so
    background tasks bind to the test engine instead of the dev database.
    """
    return AsyncSessionFactory


async def close_db_connection() -> None:
    """Dispose of the async engine's connection pool.

    Call from the FastAPI lifespan shutdown handler in `main.py`:
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            yield
            await close_db_connection()
    """
    await async_engine.dispose()
