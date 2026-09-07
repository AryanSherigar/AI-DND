import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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
    # NOTE: builds the MemoryEngine once, before any request is served, so
    # concurrent requests never race each other into building duplicate
    # connection pools / embedding models via routes.py's lazy fallback.
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


@app.get("/v1/memory/stream")
async def stream_graph(request: Request):
    if streamer.loop is None:
        streamer.loop = asyncio.get_running_loop()

    q = streamer.add_queue()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            streamer.remove_queue(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
