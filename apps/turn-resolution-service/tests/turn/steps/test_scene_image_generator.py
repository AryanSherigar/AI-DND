"""Unit tests for scene_image_generator: prompt grounding and failure handling."""

from app.exceptions.turn_exceptions import SceneImageGenerationError
from app.integrations import image_gen_client, storage_client
from app.turn.steps import scene_image_generator


def test_find_location_entity_matches_location_by_id() -> None:
    snapshot = {
        "entities": [
            {"entity_id": "loc-1", "entity_type": "location", "canonical_name": "Keep"},
            {
                "entity_id": "char-1",
                "entity_type": "character",
                "canonical_name": "Bob",
            },
        ]
    }

    found = scene_image_generator.find_location_entity(snapshot, "loc-1")

    assert found is not None
    assert found["canonical_name"] == "Keep"


def test_find_location_entity_returns_none_when_no_current_location() -> None:
    snapshot = {"entities": []}

    assert scene_image_generator.find_location_entity(snapshot, None) is None


def test_find_location_entity_returns_none_when_no_match() -> None:
    snapshot = {
        "entities": [
            {"entity_id": "loc-1", "entity_type": "location", "canonical_name": "Keep"}
        ]
    }

    assert scene_image_generator.find_location_entity(snapshot, "loc-999") is None


async def test_generate_scene_image_success_includes_location_and_prior_prompt(
    monkeypatch,
) -> None:
    captured_prompts: list[str] = []

    async def fake_generate_image(prompt: str, timeout_seconds: int) -> bytes:
        captured_prompts.append(prompt)
        return b"fake-bytes"

    async def fake_upload_image(
        content: bytes, content_type: str, object_key: str
    ) -> str:
        return f"https://storage.googleapis.com/fake-bucket/{object_key}"

    monkeypatch.setattr(image_gen_client, "generate_image", fake_generate_image)
    monkeypatch.setattr(storage_client, "upload_image", fake_upload_image)

    location = {"canonical_name": "The Sunken Keep", "description": "A ruined tower."}
    result = await scene_image_generator.generate_scene_image(
        "You step into the flooded hall.", location, "earlier prompt text", 5
    )

    assert result is not None
    url, composed_prompt = result
    assert url.startswith("https://storage.googleapis.com/fake-bucket/scene-images/")
    assert "The Sunken Keep" in composed_prompt
    assert "earlier prompt text" in composed_prompt
    assert "You step into the flooded hall." in composed_prompt
    assert captured_prompts == [composed_prompt]


async def test_generate_scene_image_generation_failure_returns_none(
    monkeypatch,
) -> None:
    async def fake_generate_image(prompt: str, timeout_seconds: int) -> bytes:
        raise SceneImageGenerationError()

    monkeypatch.setattr(image_gen_client, "generate_image", fake_generate_image)

    result = await scene_image_generator.generate_scene_image(
        "narration", None, None, 5
    )

    assert result is None


async def test_generate_scene_image_upload_failure_returns_none(monkeypatch) -> None:
    async def fake_generate_image(prompt: str, timeout_seconds: int) -> bytes:
        return b"fake-bytes"

    async def fake_upload_image(
        content: bytes, content_type: str, object_key: str
    ) -> str:
        raise SceneImageGenerationError("upload failed")

    monkeypatch.setattr(image_gen_client, "generate_image", fake_generate_image)
    monkeypatch.setattr(storage_client, "upload_image", fake_upload_image)

    result = await scene_image_generator.generate_scene_image(
        "narration", None, None, 5
    )

    assert result is None
