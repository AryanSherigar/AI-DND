"""Integration tests for database connection and session management in TRS."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import close_db_connection, get_db_session

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_get_db_session_yields_session() -> None:
    """Verify get_db_session yields an active AsyncSession and executes SELECT 1."""
    async for session in get_db_session():
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


async def test_get_db_session_rollback_on_exception() -> None:
    """Verify transaction rollback occurs when an exception is raised in session block."""
    with pytest.raises(RuntimeError, match="Simulated exception"):
        async for session in get_db_session():
            await session.execute(text("SELECT 1"))
            raise RuntimeError("Simulated exception")


async def test_close_db_connection_disposes_engine() -> None:
    """Verify close_db_connection disposes the engine pool cleanly."""
    await close_db_connection()
