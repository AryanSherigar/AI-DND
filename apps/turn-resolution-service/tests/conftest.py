"""Shared pytest fixtures for Turn Resolution Service tests."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.base import Base

settings.environment = "testing"

TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/aidnd_test_db"
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create TRS's mirrored schema in an isolated test database for the session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide a session bound to the test engine, isolated per test."""
    async_session = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for router-level integration tests, bound to the test DB session."""
    from app.db.connection import get_db_session
    from app.main import app as fastapi_app

    async def override_get_db_session():
        yield db_session

    fastapi_app.dependency_overrides[get_db_session] = override_get_db_session
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://testserver"
    ) as client:
        yield client
    fastapi_app.dependency_overrides.clear()
