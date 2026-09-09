"""Unit tests for the built-in default mood track resolution."""

from app.config import settings
from app.db.models.scenario_music import MOOD_SLOTS
from app.services import default_music


def test_all_default_track_urls_covers_every_mood():
    urls = default_music.all_default_track_urls()
    assert set(urls) == set(MOOD_SLOTS)
    assert all(urls[mood] for mood in MOOD_SLOTS)


def test_default_track_url_uses_local_upload_path_in_development(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "gcs_bucket_name", "")
    monkeypatch.setattr(settings, "core_api_public_url", "http://localhost:8000")

    assert default_music.default_track_url("peaceful") == (
        "http://localhost:8000/uploads/default-music/peaceful.mp3"
    )


def test_default_track_url_uses_gcs_path_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "gcs_bucket_name", "aidnd-prod-bucket")

    assert default_music.default_track_url("triumph") == (
        "https://storage.googleapis.com/aidnd-prod-bucket/default-music/triumph.mp3"
    )
