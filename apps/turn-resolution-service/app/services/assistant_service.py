"""Service layer for Studio AI Assistant chat and world-building guidance."""

import json
from collections.abc import AsyncIterator

import structlog
from google.genai import types
from sse_starlette.sse import ServerSentEvent

from app.exceptions.turn_exceptions import GeminiUnavailableError
from app.integrations import gemini_client
from app.models.assistant import (
    AssistantChatMessage,
    AssistantChatRequest,
    AssistantDraftContext,
)

logger = structlog.get_logger()

_BASE_PERSONA = (
    "You are an immersive world-building co-author and narrative consultant "
    "for AI-driven text RPG adventures. You help creators craft evocative, "
    "cohesive scenario settings, factions, characters, conflicts, and opening scenes. "
    "Adapt your voice and suggestions to the creator's genre and themes."
)

_ACTION_SYNTAX_GUIDE = (
    "\n\nACTION BLOCKS:\n"
    "When you propose concrete content that the creator can insert directly into "
    "their scenario draft, format that content inside a custom code block with the "
    "appropriate action tag:\n"
    "- ```action:title\\n<scenario title>\\n```\n"
    "- ```action:logline\\n<scenario logline / summary>\\n```\n"
    "- ```action:lore\\n<world lore text>\\n```\n"
    "- ```action:opening_prompt\\n<opening scene prompt>\\n```\n"
    "- ```action:conflict\\n<main conflict or goal>\\n```\n"
    '- ```action:story_card {"type": "Character"|"Faction"|"Location"|"Item", "name": "<Card Name>"}\\n<card description>\\n```\n'
    "- ```action:style\\n<narrative style and vibe>\\n```\n"
    "- ```action:instructions\\n<AI narrator rules and constraints>\\n```\n\n"
    "Use standard conversational markdown for discussion, feedback, and brainstorming. "
    "Use the action blocks whenever you offer ready-to-use draft snippets."
)


def _format_draft_summary(draft: AssistantDraftContext) -> str:
    """Format the current scenario draft fields into readable context."""
    lines = [
        f"Title: {draft.title or '(Untitled)'}",
        f"Logline: {draft.logline or '(None)'}",
        f"Genre Tags: {', '.join(draft.genre_tags) if draft.genre_tags else '(None)'}",
        f"Complexity: {draft.complexity_tier}",
        f"Player Support: {draft.player_count_support}",
        f"Estimated Playtime: {draft.estimated_playtime or '(Unset)'}",
        f"World Lore: {draft.world_lore or draft.single_lore_prompt or '(Empty)'}",
        f"Opening Prompt: {draft.opening_prompt or '(Empty)'}",
        f"Main Conflict: {draft.main_conflict or '(None)'}",
        f"Narrative Style: {draft.narrative_style or '(Default)'}",
        f"AI Instructions: {draft.ai_instructions or '(Default)'}",
        f"Active Wizard Section: {draft.active_section}",
    ]
    if draft.story_cards:
        cards = [f"- [{c.type}] {c.name}: {c.content}" for c in draft.story_cards]
        lines.append("Story Cards:\n" + "\n".join(cards))
    return "\n".join(lines)


def build_system_instruction(draft: AssistantDraftContext | None) -> str:
    """Compose the system instruction combining persona, draft context, and actions."""
    parts = [_BASE_PERSONA]
    if draft is not None:
        parts.append(
            "\nCURRENT SCENARIO DRAFT IN STUDIO:\n" + _format_draft_summary(draft)
        )
    parts.append(_ACTION_SYNTAX_GUIDE)
    return "\n".join(parts)


def format_chat_contents(
    messages: list[AssistantChatMessage],
) -> list[types.Content]:
    """Convert API messages into google-genai Content structures."""
    contents: list[types.Content] = []
    for msg in messages:
        role = "model" if msg.role == "assistant" else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.content)],
            )
        )
    return contents


async def stream_assistant_chat(
    request: AssistantChatRequest,
) -> AsyncIterator[ServerSentEvent]:
    """Stream SSE chunks for the studio assistant conversation."""
    instruction = build_system_instruction(request.draft_context)
    contents = format_chat_contents(request.messages)
    try:
        async for chunk in gemini_client.stream_chat(
            system_instruction=instruction,
            contents=contents,
            timeout_seconds=60,
            max_output_tokens=2048,
        ):
            yield ServerSentEvent(event="chunk", data=chunk)
        yield ServerSentEvent(event="done", data="")
    except GeminiUnavailableError as exc:
        logger.warning("studio_assistant_gemini_unavailable", error=str(exc))
        yield ServerSentEvent(
            event="error",
            data=json.dumps({"detail": "AI assistant is temporarily unavailable."}),
        )
