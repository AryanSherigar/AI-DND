"""FastAPI router for the public built-in default mood tracks."""

from fastapi import APIRouter

from app.models.music import DefaultMusicTracksResponse
from app.services import default_music

router = APIRouter(prefix="/v1/music", tags=["Music Defaults"])


@router.get("/defaults", response_model=DefaultMusicTracksResponse)
async def get_default_music_tracks() -> DefaultMusicTracksResponse:
    """Public: the 6 canonical built-in default track URLs, keyed by mood."""
    return DefaultMusicTracksResponse(tracks=default_music.all_default_track_urls())
