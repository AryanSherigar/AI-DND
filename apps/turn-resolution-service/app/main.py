"""Turn Resolution Service FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.connection import close_db_connection
from app.logging_config import configure_logging
from app.middleware.error_handler import setup_error_handlers
from app.middleware.request_context import request_context_middleware
from app.routers import session, turn

configure_logging(settings.log_level, settings.log_format)


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

# Required now that this service has a real HTTP entrypoint the frontend
# calls directly from the browser (POST /v1/turn, session SSE) — previously
# unnecessary since nothing outside tests reached this app over HTTP.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_context_middleware)

setup_error_handlers(app)
app.include_router(turn.router)
app.include_router(session.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
