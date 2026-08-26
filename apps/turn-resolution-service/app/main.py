"""Turn Resolution Service FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.db.connection import close_db_connection
from fastapi import FastAPI
from app.middleware.error_handler import setup_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager handling startup and shutdown events."""
    yield
    await close_db_connection()


app = FastAPI(
    title="Turn Resolution Service",
    description="Turn Resolution Service for AI-DND platform",
    version="0.1.0",
    lifespan=lifespan,
)

setup_error_handlers(app)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
