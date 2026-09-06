"""Unit tests for assistant_service."""

from app.models.assistant import (
    AssistantChatMessage,
    AssistantChatRequest,
    AssistantDraftContext,
    AssistantEntitySummary,
    AssistantMasterContext,
    AssistantStoryCard,
)
from app.services.assistant_service import (
    build_system_instruction,
    format_chat_contents,
)


def test_build_system_instruction_without_draft() -> None:
    request = AssistantChatRequest(messages=[])
    instruction = build_system_instruction(request)
    assert "You are an immersive world-building co-author" in instruction
    assert "ACTION BLOCKS:" in instruction


def test_build_system_instruction_with_draft() -> None:
    draft = AssistantDraftContext(
        title="Chronicles of Elyria",
        genre_tags=["Dark Fantasy", "Gothic"],
        world_lore="Ancient dragons ruled the sky.",
        story_cards=[
            AssistantStoryCard(
                type="Faction", name="Silver Dawn", content="Holy knights"
            )
        ],
        active_section="lore",
    )
    request = AssistantChatRequest(messages=[], draft_context=draft)
    instruction = build_system_instruction(request)
    assert "Chronicles of Elyria" in instruction
    assert "Dark Fantasy, Gothic" in instruction
    assert "Silver Dawn" in instruction
    assert "Active Wizard Section: lore" in instruction


def test_build_system_instruction_master_mode_with_context() -> None:
    context = AssistantMasterContext(
        title="Sunken Kingdom",
        active_tab="entities",
        entities=[
            AssistantEntitySummary(
                entity_id="entity-1",
                entity_type="character",
                canonical_name="Hero",
            )
        ],
    )
    request = AssistantChatRequest(messages=[], mode="master", master_context=context)
    instruction = build_system_instruction(request)
    assert "game systems designer" in instruction
    assert "Sunken Kingdom" in instruction
    assert "Hero" in instruction
    assert "action:entity" in instruction
    assert "world-building co-author" not in instruction


def test_build_system_instruction_master_mode_without_context() -> None:
    request = AssistantChatRequest(messages=[], mode="master")
    instruction = build_system_instruction(request)
    assert "game systems designer" in instruction
    assert "action:fact" in instruction


def test_format_chat_contents() -> None:
    messages = [
        AssistantChatMessage(role="user", content="Hi!"),
        AssistantChatMessage(role="assistant", content="Greetings creator."),
    ]
    contents = format_chat_contents(messages)
    assert len(contents) == 2
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Hi!"
    assert contents[1].role == "model"
    assert contents[1].parts[0].text == "Greetings creator."
