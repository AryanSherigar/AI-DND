"""Tests for music_gen_client: pure crossfade-guardrail math and the Lyria
predict call itself."""

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions.music_exceptions import MusicGenerationError
from app.integrations import music_gen_client


def test_target_bpm_uses_mood_range_midpoint() -> None:
    assert music_gen_client._target_bpm("peaceful") == 62
    assert music_gen_client._target_bpm("combat") == 120


def test_build_prompt_pins_key_and_bpm() -> None:
    prompt = music_gen_client._build_prompt("a tense chase", "tension", 95)
    assert "D minor" in prompt
    assert "95 BPM" in prompt
    assert "a tense chase" in prompt


def _fake_predict_response(audio_content: str = "ZmFrZS13YXY=") -> AsyncMock:
    body = json.dumps({"predictions": [{"bytesBase64Encoded": audio_content}]})
    response = AsyncMock()
    response.body = body
    return response


@pytest.mark.asyncio
async def test_generate_music_calls_predict_and_decodes_audio() -> None:
    audio_b64 = base64.b64encode(b"fake-audio-bytes").decode()
    fake_client = AsyncMock()
    fake_client.async_request = AsyncMock(
        return_value=_fake_predict_response(audio_b64)
    )

    with patch.object(music_gen_client, "_get_client") as mock_get_client:
        mock_get_client.return_value._api_client = fake_client
        audio_bytes, metadata = await music_gen_client.generate_music(
            prompt="a driving battle theme",
            mood="combat",
            timeout_seconds=60,
        )

    assert audio_bytes == b"fake-audio-bytes"
    assert metadata.key == "D minor"
    assert metadata.bpm == 120

    call_args = fake_client.async_request.call_args
    assert call_args.args[0] == "post"
    assert call_args.args[1].endswith(":predict")
    request_dict = call_args.args[2]
    assert request_dict["instances"][0]["prompt"].startswith("a driving battle theme")
    assert request_dict["parameters"]["sample_count"] == 1


@pytest.mark.asyncio
async def test_generate_music_raises_on_empty_predictions() -> None:
    fake_client = AsyncMock()
    fake_client.async_request = AsyncMock(
        return_value=AsyncMock(body=json.dumps({"predictions": []}))
    )

    with patch.object(music_gen_client, "_get_client") as mock_get_client:
        mock_get_client.return_value._api_client = fake_client
        with pytest.raises(MusicGenerationError):
            await music_gen_client.generate_music(
                prompt="a driving battle theme",
                mood="combat",
                timeout_seconds=60,
            )
