"""Generates a scene image for a 'see' action turn.

A missing scene image must never fail or degrade a turn — this module never
raises into the pipeline (mirrors the swallow-and-log pattern
pipeline.py's _prewarm_replit_url uses for its own best-effort side effect).
"""

import uuid

import structlog
from app.exceptions.turn_exceptions import SceneImageGenerationError
from app.integrations import image_gen_client, storage_client

logger = structlog.get_logger()

EVENT_SCENE_IMAGE_GENERATION_FAILED = "scene_image_generation_failed"

_LOCATION_ENTITY_TYPE = "location"
_NO_TEXT_INSTRUCTION = "No text or lettering in the image."


def find_location_entity(
    scenario_snapshot: dict[str, object], current_location_id: object
) -> dict[str, object] | None:
    """Look up the current location's entity in the already-denormalized
    scenario_snapshot['entities'] list — no DB/HTTP call needed. Returns
    None in newbie mode (no entity graph) or when the id has no match."""
    if not current_location_id:
        return None
    entities = scenario_snapshot.get("entities", []) or []
    for entity in entities:
        if (
            entity.get("entity_type") == _LOCATION_ENTITY_TYPE
            and entity.get("entity_id") == current_location_id
        ):
            return entity
    return None


def _build_prompt(
    narration_text: str,
    location: dict[str, object] | None,
    prior_prompt: str | None,
) -> str:
    """Compose the image prompt from location grounding, prior-scene
    consistency, and this turn's narration."""
    parts: list[str] = []
    if location:
        name = location.get("canonical_name")
        description = location.get("description")
        parts.append(
            f"Setting: {name}. {description}" if description else f"Setting: {name}."
        )
    if prior_prompt:
        parts.append(
            f"Maintain visual consistency with the earlier depiction of this "
            f"location, previously generated from: {prior_prompt}"
        )
    parts.append(f"Scene: {narration_text}")
    parts.append(_NO_TEXT_INSTRUCTION)
    return " ".join(parts)


async def generate_scene_image(
    narration_text: str,
    location: dict[str, object] | None,
    prior_prompt: str | None,
    timeout_seconds: int,
) -> tuple[str, str] | None:
    """Generate and upload a scene image for a 'see' action turn.

    Returns (image_url, composed_prompt) on success, or None on any failure
    — this step never raises into the pipeline.
    """
    prompt = _build_prompt(narration_text, location, prior_prompt)
    try:
        image_bytes = await image_gen_client.generate_image(prompt, timeout_seconds)
        object_key = f"scene-images/{uuid.uuid4()}.png"
        image_url = await storage_client.upload_image(
            image_bytes, "image/png", object_key
        )
    except SceneImageGenerationError:
        logger.warning(EVENT_SCENE_IMAGE_GENERATION_FAILED, exc_info=True)
        return None
    return image_url, prompt
