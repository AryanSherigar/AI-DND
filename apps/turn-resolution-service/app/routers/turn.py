"""FastAPI router for the live turn-resolution endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.connection import get_db_session
from app.middleware.auth import get_current_user
from app.models.auth import CurrentUser
from app.models.turn import TurnRequestInput
from app.turn.pipeline import run_turn

router = APIRouter(prefix="/v1/turn", tags=["Turn"])


@router.post("", response_model=None)
async def submit_turn(
    turn_input: TurnRequestInput,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[CurrentUser, Depends(get_current_user)],
) -> EventSourceResponse:
    """Submit a player action and stream back narration over SSE."""
    return await run_turn(turn_input, session)
