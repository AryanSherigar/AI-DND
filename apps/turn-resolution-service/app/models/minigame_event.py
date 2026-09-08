"""Play-time minigame SSE payload and result-submission shapes.

Mirrors the frontend types in shared/types/minigame.types.ts
(MinigameEventPayload, MinigameResultPayload) — see
docs/specs/master-mode-minigames.spec.md §3.4. MinigameEventPayload
intentionally excludes win_mutation/lose_mutation/tiered_outcomes/
timeout_mutation/narrator_instruction_template — those stay server-side
only, never sent to the client (§3.6 "Always" boundary).
"""

from typing import Literal

from pydantic import BaseModel, StrictInt


class MinigameEventPayload(BaseModel):
    """The play-time config handed to the client when a minigame triggers."""

    minigame_id: str
    attempt_id: str
    minigame_type: str
    label: str
    dodge_config: dict[str, object] | None = None
    replit_embed_url: str | None = None
    timeout_seconds: int


class MinigameResultInput(BaseModel):
    """A player's submitted minigame outcome, as TurnRequestInput.minigame_result."""

    minigame_id: str
    outcome_tag: Literal["win", "lose", "timeout"]
    # Strict prevents bools and lossy numeric coercion from selecting a tier.
    score: StrictInt | None = None
    attempt_id: str | None = None
