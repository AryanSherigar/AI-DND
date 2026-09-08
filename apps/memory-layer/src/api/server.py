import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routes import require_api_key, router
from api.stream import streamer
from context_memory.composition import build_memory_engine
from context_memory.core.logging import get_logger, setup_logging
from context_memory.ingestion.graph_writer import GraphWriter

setup_logging()
logger = get_logger("api.server")

# Monkey Patch GraphWriter to intercept writes
original_write = GraphWriter.write


def patched_write(self, plan):
    res = original_write(self, plan)
    try:
        streamer.broadcast_plan(plan)
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
    return res


GraphWriter.write = patched_write


@asynccontextmanager
async def lifespan(app: FastAPI):
    # HIGH-01 fix: this is the ONLY place a MemoryEngine gets built --
    # routes.py's `get_engine` dependency reads `app.state.engine` rather
    # than lazily building its own, so no duplicate connection pools /
    # embedding models are ever created.
    app.state.engine = await asyncio.to_thread(build_memory_engine)
    yield


app = FastAPI(title="Context Memory API", lifespan=lifespan)

# §12 fix: was `allow_origins=["*"]` + `allow_credentials=True` -- Starlette's
# CORSMiddleware reflects the request's own Origin header back (rather than
# a literal "*") whenever credentials are allowed, so this combination
# actually permitted credentialed cross-origin requests from ANY origin, not
# a harmless wildcard. `CONTEXT_MEMORY_ALLOWED_ORIGINS` (a JSON array string)
# is empty by default -- no browser origin is allowed, and credentials are
# never enabled, until an operator explicitly configures real origins.
# Non-browser server-to-server callers (AI-DND's own backend services) are
# unaffected either way -- CORS only restricts browser-issued cross-origin
# requests, never direct API calls.
_raw_allowed_origins = os.environ.get("CONTEXT_MEMORY_ALLOWED_ORIGINS", "").strip()
_allowed_origins = json.loads(_raw_allowed_origins) if _raw_allowed_origins else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=bool(_allowed_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    logger.info(
        "HTTP %s %s -> status=%d duration=%.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(router, dependencies=[Depends(require_api_key)])


# Liveness probe for orchestrators and container healthchecks.
# Deliberately NOT behind `require_api_key` -- infra liveness probes
# hitting this bare path shouldn't need credentials.
# Deep readiness checks (Postgres/HydraDB) live at `/v1/health`.
@app.get("/health")
async def read_health() -> dict[str, str]:
    """Lightweight liveness probe."""
    return {"status": "ok"}


# CRIT-01 fix: `/v1/memory/stream` moved to api/routes.py's `router` (see
# stream_graph there) so it inherits `require_api_key` and is scoped to a
# single tenant's context_id, instead of living here unauthenticated.
