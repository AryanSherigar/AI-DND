import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.base import BaseAppException

logger = structlog.get_logger()


def setup_error_handlers(app: FastAPI):
    @app.exception_handler(BaseAppException)
    async def app_exception_handler(request: Request, exc: BaseAppException):
        logger.warning("domain_exception", path=request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
