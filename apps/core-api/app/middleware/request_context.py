"""Request-scoped correlation ID binding and request start/end logging.

Supersedes the previously-empty app/middleware/logging.py stub: binding the
request ID as a structlog contextvar and logging the request's lifecycle are
two facets of the same job (every log line emitted while handling this
request should carry the ID), so they live in one middleware function rather
than two differently-named files.
"""

import time
import uuid

import structlog
from fastapi import Request, Response

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
