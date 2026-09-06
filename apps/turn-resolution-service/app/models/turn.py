"""Pydantic request/response and internal step-boundary shapes for turn resolution."""

import uuid
from typing import Literal

from pydantic import BaseModel

from app.models.minigame_event import MinigameResultInput


class TurnRequestInput(BaseModel):
    """Raw input to the turn pipeline."""

    playthrough_id: uuid.UUID
    participant_id: uuid.UUID
    action_text: str
    action_kind: Literal["narrative", "minigame_result"] = "narrative"
    minigame_result: MinigameResultInput | None = None


class TurnRequest(TurnRequestInput):
    """Validated turn request, produced by request_receiver."""

    turn_count: int


class LoadedState(BaseModel):
    """Scenario snapshot and playthrough state, produced by state_loader."""

    scenario_id: uuid.UUID
    scenario_snapshot: dict[str, object]
    state: dict[str, object]
    turn_count: int
    checkpoint: str | None
    is_playtest: bool = False
