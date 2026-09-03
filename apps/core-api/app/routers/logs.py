"""FastAPI router for client-side (frontend) log ingestion."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.db.models.user import User
from app.middleware.auth import get_optional_current_user
from app.models.logs import ClientLogBatch
from app.services.log_ingestion_service import LogIngestionService

router = APIRouter(prefix="/v1/logs", tags=["logs"])


def get_log_ingestion_service() -> LogIngestionService:
    """Dependency injector for LogIngestionService."""
    return LogIngestionService()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_client_logs(
    batch: ClientLogBatch,
    user: Annotated[User | None, Depends(get_optional_current_user)],
    service: Annotated[LogIngestionService, Depends(get_log_ingestion_service)],
) -> None:
    """Accept a batch of client-side log events. Auth optional (pre-login errors too)."""
    service.ingest_batch(batch, user_id=user.user_id if user else None)
