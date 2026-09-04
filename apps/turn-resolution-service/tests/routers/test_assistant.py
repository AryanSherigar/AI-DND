"""Integration tests for Studio Assistant endpoint POST /v1/studio/assistant."""

import uuid
from collections.abc import AsyncIterator

from google.genai import types
from httpx import AsyncClient

from app.exceptions.turn_exceptions import GeminiUnavailableError
from app.integrations import gemini_client


def _make_auth_headers() -> dict[str, str]:
    return {"X-Dev-User-Id": str(uuid.uuid4())}


async def test_assistant_chat_requires_auth(async_client: AsyncClient) -> None:
    payload = {"messages": [{"role": "user", "content": "Help me with lore"}]}
    response = await async_client.post("/v1/studio/assistant", json=payload)
    assert response.status_code == 401


async def test_assistant_chat_streams_chunks_and_done(
    async_client: AsyncClient, monkeypatch
) -> None:
    async def fake_stream_chat(
        system_instruction: str,
        contents: list[types.Content],
        timeout_seconds: int,
        max_output_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        yield "Welcome to "
        yield "the forgotten realm."

    monkeypatch.setattr(gemini_client, "stream_chat", fake_stream_chat)

    payload = {
        "messages": [{"role": "user", "content": "Give me world intro"}],
        "draft_context": {
            "title": "Sunken Kingdom",
            "active_section": "lore",
        },
    }
    response = await async_client.post(
        "/v1/studio/assistant",
        json=payload,
        headers=_make_auth_headers(),
    )
    assert response.status_code == 200
    body = response.text
    assert "event: chunk\r\ndata: Welcome to " in body or "data: Welcome to " in body
    assert "event: done\r\ndata: " in body or "done" in body


async def test_assistant_chat_handles_gemini_unavailable(
    async_client: AsyncClient, monkeypatch
) -> None:
    async def failing_stream_chat(
        system_instruction: str,
        contents: list[types.Content],
        timeout_seconds: int,
        max_output_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        raise GeminiUnavailableError()
        yield ""

    monkeypatch.setattr(gemini_client, "stream_chat", failing_stream_chat)

    payload = {
        "messages": [{"role": "user", "content": "Hello"}],
    }
    response = await async_client.post(
        "/v1/studio/assistant",
        json=payload,
        headers=_make_auth_headers(),
    )
    assert response.status_code == 200
    assert "event: error" in response.text
