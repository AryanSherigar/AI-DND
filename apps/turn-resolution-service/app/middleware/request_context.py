"""Request-scoped correlation ID binding and request start/end logging.

Supersedes what an empty middleware/logging.py stub would have been: binding
the request ID as a structlog contextvar and logging the request's lifecycle
are two facets of the same job, so they live in one middleware function.
"""

import time
import uuid

import structlog
from fastapi import Request, Response
from sse_starlette.sse import EventSourceResponse

REQUEST_ID_HEADER = "X-Request-Id"
EVENT_REQUEST_STARTED = "request_started"
EVENT_REQUEST_COMPLETED = "request_completed"

logger = structlog.get_logger()


async def request_context_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    logger.info(EVENT_REQUEST_STARTED, method=request.method, path=request.url.path)
    start = time.monotonic()
    response = await call_next(request)

    # NOTE: SSE responses stream their body (and therefore most of their
    # actual work) after call_next returns, inside the pipeline's own
    # generator — request_completed here would fire before the turn/stream
    # has actually run. pipeline.py owns sse_stream_opened/closed/error
    # instead; this middleware only logs completion for non-streaming routes.
    if not isinstance(response, EventSourceResponse):
        _log_request_completed(request, response, start)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def _log_request_completed(request: Request, response: Response, start: float) -> None:
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        EVENT_REQUEST_COMPLETED,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
