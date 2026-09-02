"""Shared pytest fixtures for Turn Resolution Service tests."""

import pytest_asyncio
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
