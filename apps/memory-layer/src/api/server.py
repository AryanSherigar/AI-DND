import os
import time
import asyncio
import json
from fastapi import Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from api.routes import health_check, require_api_key, router
from context_memory.core.logging import get_logger, setup_logging
from context_memory.ingestion.graph_writer import GraphWriter
from api.stream import streamer

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

app = FastAPI(title="Context Memory API")

# §12 fix: was `allow_origins=["*"]` + `allow_credentials=True` -- Starlette's
# CORSMiddleware reflects the request's own Origin header back (rather than
# a literal "*") whenever credentials are allowed, so this combination
# actually permitted credentialed cross-origin requests from ANY origin, not
# a harmless wildcard. `CONTEXT_MEMORY_ALLOWED_ORIGINS` (comma-separated) is
# empty by default -- no browser origin is allowed, and credentials are
# never enabled, until an operator explicitly configures real origins.
# Non-browser server-to-server callers (AI-DND's own backend services) are
# unaffected either way -- CORS only restricts browser-issued cross-origin
# requests, never direct API calls.
_allowed_origins = [o.strip() for o in os.environ.get("CONTEXT_MEMORY_ALLOWED_ORIGINS", "").split(",") if o.strip()]

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

# §12 fix: was `return {"status": "ok"}` unconditionally, no checks at all
# -- a liveness probe that could never report anything but healthy.
# Delegates to the same real Postgres/HydraDB checks `/v1/health` runs
# (routes.py's `health_check`) instead of a second, parallel "always ok"
# implementation. Deliberately NOT behind `require_api_key` -- infra
# liveness/readiness probes hitting this bare, conventional path shouldn't
# need a credential, even when one is configured for the rest of the API.
@app.get("/health")
def read_health():
    return health_check()

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
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            streamer.remove_queue(q)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
