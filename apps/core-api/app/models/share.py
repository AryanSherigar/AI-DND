"""Pydantic request/response schemas for playthrough sharing."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ShareMode = Literal["spectate", "join"]


class ShareCreate(BaseModel):
    """Payload to generate (or fetch an existing) share link for a playthrough."""

    mode: ShareMode


class ShareResponse(BaseModel):
    """A share link's token and full shareable URL."""

    model_config = ConfigDict(from_attributes=True)

    share_id: uuid.UUID
    share_token: str
    mode: ShareMode
    playthrough_id: uuid.UUID
    url: str
    created_at: datetime


class JoinRequest(BaseModel):
    """Payload to join a playthrough via a join-mode share token."""

    share_token: str
