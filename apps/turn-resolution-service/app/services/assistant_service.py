"""Service layer for Studio AI Assistant chat and world-building guidance."""

import json
import re
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
    AssistantMasterContext,
)
from app.services.expression_validator import (
    build_available_field_paths,
    validate_expression_tree,
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

_MASTER_BASE_PERSONA = (
    "You are a game systems designer and consistency-checking collaborator for "
    "a structured, tool-driven text RPG engine. You help creators build out "
    "entities (characters, locations, items, factions, organizations), the facts "
    "that connect them, and the tracked state values that drive gameplay. You "
    "care about internal consistency (no contradicting facts, no orphaned "
    "references), sensible balance, and clear win/lose logic. Adapt your voice "
    "and suggestions to the creator's genre and themes, but always prioritize "
    "structural correctness over flourish."
)

_MASTER_ACTION_SYNTAX_GUIDE = (
    "\n\nACTION BLOCKS:\n"
    "When you propose concrete structured data the creator can add directly to "
    "their scenario, format it inside a custom code block with the appropriate "
    "action tag. The block content must be valid JSON matching the shape shown:\n"
    "Every field the block needs — including temp_id, key, or a delete op — "
    "goes INSIDE that single JSON object. Never put anything on the fence "
    "line itself (no ```action:entity {...} on one line); always a bare "
    "```action:<target> fence, then one JSON object on the following lines.\n"
    "- ```action:entity\\n"
    '{"temp_id": "<short_local_id, optional>", "entity_type": '
    '"character"|"location"|"item"|"faction"|"organization", '
    '"canonical_name": "<name>", "aliases": [], "description": "<text>", '
    '"attributes_schema": {}}\\n```\n'
    "  temp_id is optional and only needed if a fact in this same reply will "
    "  reference this brand-new entity before it has a real ID.\n"
    "  attributes_schema maps each attribute name to a field definition object "
    '{"type": "string"|"number"|"boolean"|"enum", "initial": <matching value>} '
    "— never a bare value directly. Omit attributes_schema entirely (or leave it "
    "{}) rather than guess at a shape you're not sure of.\n"
    "  Example with attributes:\n"
    "  ```action:entity\n"
    '  {"temp_id": "guard_captain", "entity_type": "character", '
    '"canonical_name": "Guard Captain", "description": "Commands the palace '
    'guard.", "attributes_schema": {"loyalty": {"type": "number", "initial": '
    '50}, "rank": {"type": "string", "initial": "Captain"}}}\n'
    "  ```\n"
    "  To delete an existing entity instead: "
    '```action:entity\\n{"op": "delete", "entity_id": "<existing entity_id>"}'
    "\\n```\n"
    "- ```action:fact\\n"
    '{"subject_ref": "<temp_id or existing entity_id>", "predicate": "<verb phrase>", '
    '"object_ref": "<temp_id or existing entity_id, omit if using object_literal>", '
    '"object_literal": "<text, omit if using object_ref>", "hidden": false}\\n```\n'
    "  Use subject_ref/object_ref to point at an entity already listed in the "
    "  current scenario context (its real entity_id) or at a temp_id you just "
    "  assigned to a new entity earlier in this same reply.\n"
    "  To delete an existing fact instead: "
    '```action:fact\\n{"op": "delete", "fact_id": "<existing fact_id>"}\\n```\n'
    "- ```action:state_field\\n"
    '{"key": "<field_name>", "type": "string"|"number"|"boolean"|"enum", '
    '"label": "<display label>", "initial": <value>}\\n```\n'
    "  key lives inside this same JSON object alongside type/label/initial — "
    "  never as a separate blob or a second JSON object.\n"
    "- ```action:title\\n<scenario title, max 255 characters>\\n```\n"
    "- ```action:logline\\n<scenario logline / summary, ONE sentence, "
    "max 150 characters — this is a hard limit the save will reject if exceeded>"
    "\\n```\n"
    "- ```action:opening_prompt\\n<opening scene text>\\n```\n"
    "- ```action:instructions\\n<house rules — hard world constraints the "
    "narrator must always respect>\\n```\n\n"
    "EXPRESSION TREES (conditions, invariants, end conditions):\n"
    "Each of these targets carries a `condition_expression` / `invariant_expression` "
    "built from this exact grammar — a single comparison, optionally chained to "
    "one more comparison via AND/OR/NOT:\n"
    '{"field": "<field.path>", "op": "=="|"!="|"<"|"<="|">"|">="|"in"|"contains"|"matches", '
    '"value": <literal>, "AND": {<nested expression, optional>}, '
    '"OR": {<nested expression, optional>}, "NOT": {<nested expression, optional>}}\n'
    "Only reference a `field` that appears under Tracked State Fields or as "
    "`<entity_slug>.<attribute>` under Existing Entities above — never invent one. "
    "The creator can still review and correct the expression before saving, so "
    "propose your best attempt rather than leaving it out.\n\n"
    "Worked example — trigger when the player has at least 100 gold AND is in "
    "the throne room:\n"
    "```action:condition\n"
    '{"label": "Bribe Available", "narrator_instruction": '
    '"Offer the guard a bribe option.", "condition_expression": '
    '{"field": "gold", "op": ">=", "value": 100, "AND": '
    '{"field": "current_location_id", "op": "==", "value": "throne_room"}}}\n'
    "```\n"
    "- ```action:condition\\n"
    '{"label": "<short label>", "narrator_instruction": "<what the narrator does '
    'when true>", "condition_expression": {...grammar above...}, '
    '"state_mutation": {"path": "<field.path>", "op": "set"|"increment"|"decrement", '
    '"value": <literal>}}\\n```\n'
    "  state_mutation is optional — only include it if the rule should also "
    "  directly change a tracked value when it becomes true.\n"
    "- ```action:invariant\\n"
    '{"label": "<short label>", "narrator_text": "<the constraint, stated as '
    'fact>", "applies_to": "global"|"player"|"<existing entity_id>", '
    '"invariant_expression": {...grammar above...}}\\n```\n'
    "- ```action:end_condition\\n"
    '{"outcome_tag": "win"|"lose", "outcome_title": "<short title>", '
    '"outcome_text": "<shown to the player on this ending>", "is_secret": '
    'false, "condition_expression": {...grammar above...}}\\n```\n\n'
    "Use standard conversational markdown for discussion, feedback, and "
    "brainstorming. Use the action blocks whenever you offer ready-to-apply "
    "structured suggestions, and prefer proposing several related pieces "
    "together (e.g. a faction entity plus its member entities plus the facts "
    "linking them) over one at a time."
)


def _format_master_context_summary(context: AssistantMasterContext) -> str:
    """Format the current master-mode scenario data into readable context."""
    lines = [
        f"Title: {context.title or '(Untitled)'}",
        f"Logline: {context.logline or '(None)'}",
        f"Narrator Persona: {context.narrator_persona or '(Default)'}",
        f"Opening Scene: {context.opening_scene or '(Empty)'}",
        f"Active Tab: {context.active_tab}",
    ]
    if context.state_schema:
        fields = [f"- {key}: {value}" for key, value in context.state_schema.items()]
        lines.append("Tracked State Fields:\n" + "\n".join(fields))
    if context.entities:
        entities = [
            f"- [{e.entity_type}] {e.canonical_name} (id={e.entity_id}): "
            f"{e.description or '(no description)'}"
            for e in context.entities
        ]
        lines.append("Existing Entities:\n" + "\n".join(entities))
    if context.facts:
        facts = [
            f"- {f.subject_entity_id} --{f.predicate}--> "
            f"{f.object_entity_id or f.object_literal}"
            for f in context.facts
        ]
        lines.append("Existing Facts:\n" + "\n".join(facts))
    if context.conditions:
        conditions = [f"- {c.label}" for c in context.conditions]
        lines.append("Existing Active Rules:\n" + "\n".join(conditions))
    if context.invariants:
        invariants = [f"- {i.label}" for i in context.invariants]
        lines.append("Existing Always-True Rules:\n" + "\n".join(invariants))
    if context.end_conditions:
        end_conditions = [
            f"- [{e.outcome_tag}] {e.outcome_title}" for e in context.end_conditions
        ]
        lines.append("Existing Win/Lose Conditions:\n" + "\n".join(end_conditions))
    return "\n".join(lines)


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


def build_system_instruction(request: AssistantChatRequest) -> str:
    """Compose the system instruction combining persona, scenario context, and actions."""
    if request.mode == "master":
        parts = [_MASTER_BASE_PERSONA]
        if request.master_context is not None:
            parts.append(
                "\nCURRENT MASTER-MODE SCENARIO DATA:\n"
                + _format_master_context_summary(request.master_context)
            )
        parts.append(_MASTER_ACTION_SYNTAX_GUIDE)
        return "\n".join(parts)

    parts = [_BASE_PERSONA]
    if request.draft_context is not None:
        parts.append(
            "\nCURRENT SCENARIO DRAFT IN STUDIO:\n"
            + _format_draft_summary(request.draft_context)
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


_ACTION_BLOCK_RE = re.compile(
    r"```action:([a-z_]+)(?:[ \t]+(\{[^}\n]*\}))?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)

_EXPRESSION_TARGETS = {
    "condition": "condition_expression",
    "invariant": "invariant_expression",
    "end_condition": "condition_expression",
}

# Mirrors the max_length constraints on Scenario.title/logline in
# core-api's app/models/scenario.py — checked here so an overlong AI
# suggestion is flagged before Apply triggers a 422 from that PATCH.
_TEXT_TARGET_MAX_LENGTH = {"title": 255, "logline": 150}


def _validate_expression_block(
    target: str, payload: object, master_context: AssistantMasterContext | None
) -> list[str]:
    expression_key = _EXPRESSION_TARGETS.get(target)
    if expression_key is None or master_context is None:
        return []
    available_fields = build_available_field_paths(
        master_context.state_schema, master_context.entities
    )
    expression = payload.get(expression_key) if isinstance(payload, dict) else None
    return validate_expression_tree(expression, available_fields)


def _validate_text_block(target: str, content: str) -> list[str]:
    max_length = _TEXT_TARGET_MAX_LENGTH.get(target)
    if max_length is None or len(content) <= max_length:
        return []
    message = (
        f"This is {len(content)} characters — {target} has a {max_length}-character "
        "limit. Shorten it before applying."
    )
    return [message]


def _validate_fact_refs(payload: object, known_ids: set[str]) -> list[str]:
    """Flags a fact whose subject/object references an entity that isn't
    among the ids already known (existing entities plus temp_ids assigned
    earlier in this same reply) — the create would otherwise fail with an
    opaque 'invalid UUID' error instead of this actionable one."""
    if not isinstance(payload, dict):
        return []
    errors: list[str] = []
    subject = payload.get("subject_ref") or payload.get("subject_entity_id")
    if subject and subject not in known_ids:
        errors.append(
            f"References entity '{subject}' as the subject, but no matching "
            "temp_id or existing entity_id was found — the entity may need to "
            "be created first."
        )
    if payload.get("object_literal") is None:
        obj = payload.get("object_ref") or payload.get("object_entity_id")
        if obj and obj not in known_ids:
            errors.append(
                f"References entity '{obj}' as the object, but no matching "
                "temp_id or existing entity_id was found — the entity may need "
                "to be created first."
            )
    return errors


def _find_block_validations(
    full_text: str, master_context: AssistantMasterContext | None
) -> list[dict[str, object]]:
    """Scans the completed reply for master-mode action blocks that can fail
    at apply time (a hallucinated expression field, a fact referencing an
    entity that doesn't exist, an overlong title/logline) and returns only
    the ones with errors."""
    known_entity_ids = (
        {e.entity_id for e in master_context.entities} if master_context else set()
    )
    known_ids = set(known_entity_ids)
    results: list[dict[str, object]] = []
    for index, match in enumerate(_ACTION_BLOCK_RE.finditer(full_text)):
        target = match.group(1).lower()
        raw_content = match.group(3)

        if target in _TEXT_TARGET_MAX_LENGTH:
            errors = _validate_text_block(target, raw_content.strip())
            if errors:
                results.append({"index": index, "errors": errors})
            continue

        if target not in ("entity", "fact", *_EXPRESSION_TARGETS):
            continue
        try:
            payload = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError):
            results.append(
                {"index": index, "errors": ["Suggestion is not valid JSON."]}
            )
            continue

        if target == "entity":
            # temp_id now lives inside the entity's own JSON body.
            temp_id = payload.get("temp_id") if isinstance(payload, dict) else None
            if temp_id:
                known_ids.add(temp_id)
            # attributes_schema shape issues are auto-normalized when applied
            # (useMasterActionApplier.ts), so there's nothing to flag here.
            continue
        if target == "fact":
            errors = _validate_fact_refs(payload, known_ids)
        else:
            errors = _validate_expression_block(target, payload, master_context)
        if errors:
            results.append({"index": index, "errors": errors})
    return results


async def stream_assistant_chat(
    request: AssistantChatRequest,
) -> AsyncIterator[ServerSentEvent]:
    """Stream SSE chunks for the studio assistant conversation."""
    instruction = build_system_instruction(request)
    contents = format_chat_contents(request.messages)
    full_text_parts: list[str] = []
    try:
        async for chunk in gemini_client.stream_chat(
            system_instruction=instruction,
            contents=contents,
            timeout_seconds=60,
            max_output_tokens=2048,
        ):
            full_text_parts.append(chunk)
            yield ServerSentEvent(event="chunk", data=chunk)

        block_validations = _find_block_validations(
            "".join(full_text_parts), request.master_context
        )
        done_data = (
            json.dumps({"block_validation": block_validations})
            if block_validations
            else ""
        )
        yield ServerSentEvent(event="done", data=done_data)
    except GeminiUnavailableError as exc:
        logger.warning("studio_assistant_gemini_unavailable", error=str(exc))
        yield ServerSentEvent(
            event="error",
            data=json.dumps({"detail": "AI assistant is temporarily unavailable."}),
        )
