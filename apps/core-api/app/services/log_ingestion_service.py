"""Forwards batched frontend log events into the structlog pipeline.

No repository: nothing here is persisted to a database table, each entry is
simply re-emitted as a structured log line through the same processors
(including redaction) that back-end-originated logs already flow through.
"""

import uuid

import structlog

from app.logging_config import EVENT_CATEGORY_OPERATIONAL
from app.models.logs import ClientLogBatch, ClientLogEntry

logger = structlog.get_logger()


class LogIngestionService:
    """Service re-emitting client-submitted log batches as structured log lines."""

    def ingest_batch(self, batch: ClientLogBatch, user_id: uuid.UUID | None) -> None:
        for entry in batch.entries:
            self._log_one(entry, user_id)

    def _log_one(self, entry: ClientLogEntry, user_id: uuid.UUID | None) -> None:
        bound = logger.bind(
            request_id=entry.request_id,
            user_id=str(user_id) if user_id else None,
            session_id=entry.session_id,
            event_category=EVENT_CATEGORY_OPERATIONAL,
            source="frontend",
            client_timestamp=entry.client_timestamp.isoformat(),
        )
        log_fn = getattr(bound, entry.level)
        log_fn(entry.event, **entry.fields)
