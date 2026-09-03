"""Pydantic request schemas for client-side (frontend) log ingestion."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ClientLogLevel = Literal["debug", "info", "warning", "error"]


class ClientLogEntry(BaseModel):
    """A single structured log event emitted by the frontend."""

    level: ClientLogLevel
    event: str
    request_id: str | None = None
    session_id: str
    client_timestamp: datetime
    fields: dict[str, object] = Field(default_factory=dict)


class ClientLogBatch(BaseModel):
    """A batch of client log events, flushed together by the frontend logger."""

    entries: list[ClientLogEntry] = Field(max_length=100)
