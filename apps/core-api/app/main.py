"""Core API FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.connection import close_db_connection
from app.logging_config import configure_logging
from app.middleware.error_handler import setup_error_handlers
from app.middleware.request_context import request_context_middleware
from app.routers import (
    auth,
    conditions,
    end_conditions,
    entities,
    facts,
    invariants,
    logs,
    maps,
    minigames,
    music_defaults,
    playthroughs,
    scenario_entity_types,
    scenario_music,
    scenarios,
    share,
    uploads,
    users,
)

configure_logging(settings.log_level, settings.log_format)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager handling startup and shutdown events."""
    yield
    await close_db_connection()


app = FastAPI(
    title="Core API",
    description="Core API service for AI-DND platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_context_middleware)

setup_error_handlers(app)
app.include_router(auth.router)
app.include_router(scenarios.router)
app.include_router(scenario_music.router)
app.include_router(music_defaults.router)
app.include_router(entities.router)
app.include_router(scenario_entity_types.router)
app.include_router(facts.router)
app.include_router(conditions.router)
app.include_router(end_conditions.router)
app.include_router(invariants.router)
app.include_router(maps.router)
app.include_router(minigames.router)
app.include_router(playthroughs.router)
app.include_router(share.router)
app.include_router(logs.router)
app.include_router(uploads.router)
app.include_router(users.router)

upload_dir = Path(settings.local_upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
