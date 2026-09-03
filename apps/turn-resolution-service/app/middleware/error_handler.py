import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.base import BaseAppException

logger = structlog.get_logger()

EVENT_UNHANDLED_EXCEPTION = "unhandled_exception"


def setup_error_handlers(app: FastAPI):
    @app.exception_handler(BaseAppException)
    async def app_exception_handler(request: Request, exc: BaseAppException):
        logger.warning("domain_exception", path=request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(EVENT_UNHANDLED_EXCEPTION, path=request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
