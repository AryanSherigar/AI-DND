# Spec: Play Screen Text Generation Optimization

## 1. Objective & User Outcome
- **Problem Statement:** In `apps/turn-resolution-service/`, turn text generation in `ai_orchestrator.py` suffers from several issues:
  1. The system instruction in Newbie mode consists only of the creator's `narrator_persona` (often empty or a single terse phrase), lacking fundamental Dungeon Master rules, player agency guardrails, formatting directives, or length bounds.
  2. The turn prompt interpolates raw stringified Python dictionaries (`World: {'factions': ...}`) and stringified lists of Python dicts (`Recent turns: [{'action_text': ...}, ...]`), wasting ~1,000+ input tokens per turn on punctuation and confusing the LLM's conversational turn-tracking.
  3. `turn_history_window_size` is set to 10 turns, which inflates input prompt cost and latency, even though older world facts are already indexed and retrieved by the Memory Layer.
  4. `gemini_max_output_tokens` is capped at 200 tokens with zero word count instructions in the prompt, resulting in either abrupt mid-sentence cutoffs or hurried prose.
  5. `[MOOD: <tone>]` instruction is only provided in Newbie mode, meaning Master mode never emits mood tags and the frontend adaptive audio system remains static in Master playthroughs.
- **User Story:** As a player in either Newbie or Master mode, I want immersive, evocative, second-person narration that never hijacks my character's agency, formats cleanly with double newlines for the e-book reader, transitions ambient music dynamically, and streams briskly without truncation, so that every turn feels like a premium tabletop gaming session.
- **Success Criteria:**
  - Standardized Base DM System Prompt active across all turns in both Newbie and Master modes.
  - Zero raw Python dictionary or list strings (`{...}`, `[...]`) in generated prompts.
  - Output token ceiling expanded to 350 with a strict 150-word prompt directive, eliminating mid-sentence cutoffs.
  - Turn history window reduced from 10 to 6 turns in clean dialogue format (`Player: ... \nNarrator: ...`), saving ~800–1,200 tokens per turn.
  - Master mode parses `[MOOD: <tone>]` tags from `final_text`, emitting `mood` SSE events identically to Newbie mode.
  - Temperature set to 0.75 and Top-P to 0.95.
  - 100% test coverage in `tests/turn/steps/test_ai_orchestrator.py` and zero regressions across TRS test suite.

---

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - `apps/turn-resolution-service/app/config.py`: Centralized LLM sampling and history parameters.
  - `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py`: Prompt builder, system instruction builder, and Gemini generation orchestrator.
  - `apps/turn-resolution-service/app/integrations/gemini_client.py`: Google GenAI SDK interface.
  - `apps/turn-resolution-service/app/turn/mood.py`: Tag extractor (`extract_mood_tag`).
  - `apps/frontend/src/features/play/stores/play.store.ts`: Client SSE receiver for `mood` and `narration` events.
  - `apps/frontend/src/features/play/components/PlayScreen/EBook/EBookCanvas.tsx`: Renders paragraphs split by `\n\s*\n`.

- **Sequence Flow:**
  1. **Intake & Context Retrieval**: `pipeline.py` receives turn request, loads state, and queries the Memory Layer for relevant world facts (`context: MemoryQueryResponse`).
  2. **System Instruction Assembly**:
     - `_build_system_instruction` (Newbie) or `_build_master_system_instruction` (Master) starts with `_BASE_DM_SYSTEM_PROMPT`.
     - Injects scenario-specific `narrator_persona` (or checkpoint override), condition instructions, on-scene entity guidelines, and invariants.
  3. **Turn Prompt Assembly (`_build_prompt`)**:
     - `## Setting`: Cleanly formats `world_data` (bulleted key-values if dict, trimmed text if string).
     - `## Grounded World Memory`: If facts exist, formats each fact as `- <subject> <predicate> <object>.`
     - `## Recent Story Chronicle`: Slices last `settings.turn_history_window_size` (6) turns and renders as:
       ```
       Player: <action_text>
       Narrator: <narration_text>
       ```
     - `## Current Player Action`: `Player: <action_text>`
  4. **Generation & Streaming**:
     - **Newbie Mode**: `gemini_client.stream_narration` yields chunks. `_process_stream_chunk` extracts `[MOOD: ...]` on line 1, emits SSE `mood` event to transition soundtrack, and streams clean narration chunks to frontend.
     - **Master Mode**: `gemini_client.generate_with_tools` runs tool-calling loop. When narration finishes (`final_text`), `extract_mood_tag` strips `[MOOD: ...]`, emits `mood` SSE event, and chunks clean narrative text via `_chunk_text`.

---

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Test:** `/home/aryan-sherigar/.local/bin/uv run pytest tests/turn/steps/test_ai_orchestrator.py -v`
- **Full Turn Suite:** `/home/aryan-sherigar/.local/bin/uv run pytest tests/turn/ -v`
- **Lint / Format:** `/home/aryan-sherigar/.local/bin/uv run ruff format . && /home/aryan-sherigar/.local/bin/uv run ruff check . --fix`

### 3.2. Testing Strategy & Conformance
- Test file: `apps/turn-resolution-service/tests/turn/steps/test_ai_orchestrator.py`
- Test cases:
  1. `test_system_instruction_includes_base_dm_prompt`: Verifies base rules (2nd person POV, agency guardrail, 150-word cap, double newlines) are present.
  2. `test_prompt_formats_world_data_cleanly`: Verifies dict world data is formatted without raw Python `{...}` syntax.
  3. `test_prompt_formats_history_as_dialogue_script`: Verifies turns are formatted as `Player: ...\nNarrator: ...` without raw JSON list reprs.
  4. `test_prompt_respects_history_window_size`: Verifies only the configured number of recent turns are included.
  5. `test_facts_formatted_as_bulleted_list`: Verifies facts are formatted as clean bullet points.
  6. `test_master_mode_emits_mood_and_clean_narration`: Verifies Master mode extracts `[MOOD: ...]` from `final_text`, yields a `mood` event, and yields clean narrative text without the tag.

### 3.3. Project Structure & File Layout
- **Files to Modify:**
  - `apps/turn-resolution-service/app/config.py`
  - `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py`
  - `apps/turn-resolution-service/tests/turn/steps/test_ai_orchestrator.py`
- **Documentation Created:**
  - `docs/specs/play-screen-text-generation-optimization.spec.md` (this file)

### 3.4. Code Style & Interfaces
- Enforce `CLAUDE.md`:
  - Functions under 30 lines.
  - Nesting depth max 2 levels.
  - Type annotations on every function.
  - No magic numbers: use `config.settings`.

```python
_BASE_DM_SYSTEM_PROMPT = (
    "You are the Dungeon Master and Narrator for an interactive tabletop roleplaying adventure.\n\n"
    "Core Narration Rules:\n"
    "1. Perspective: Address the player in the second person ('You').\n"
    "2. Player Agency: NEVER narrate the player character's internal thoughts, dialogue, or future actions. "
    "Only narrate the immediate sensory consequences of their action and the world's reaction.\n"
    "3. Show, Don't Tell: Reveal NPC motives, danger, and world state through sensory details, physical behaviors, tone, and environment rather than abstract exposition dumps.\n"
    "4. Fact Consistency: Strictly adhere to the Grounded World Memory facts. Treat them as unshakeable truth and never contradict established lore or previously revealed events.\n"
    "5. Length & Pacing: Limit your narration to at most 150 words across 2 to 3 concise paragraphs.\n"
    "6. UI Formatting: ALWAYS separate paragraphs with a double newline (a blank line) so chapter typography and drop-caps format properly. Never output walls of unbroken text.\n"
    "7. No Meta-Chat: Do not include meta-conversational commentary, greetings, or disclaimers (e.g., 'Certainly!', 'As a DM...', 'What would you like to do next?').\n"
    "8. Scene Mood: On the very first line of your response, specify the scene's emotional/dramatic tone formatted exactly as:\n"
    "[MOOD: <peaceful|mystery|tension|combat|melancholy>]\n"
    "Maintain the previous tone unless a significant shift occurs. On the next line, begin the narrative prose."
)
```

### 3.5. Git & Review Workflow
- Branch: `feat/optimize-text-generation`
- Review focus: Prompt efficiency, token count preservation, clean mood tag extraction in Master mode.

### 3.6. Boundaries
- ✅ **Always:** Run `ruff format`, `ruff check`, and pytest before finalizing; keep functions <= 30 lines.
- ⚠️ **Ask First:** Changing database schemas or altering SSE event names.
- 🚫 **Never:** Commit hardcoded secrets or API keys; break the `EventSourceResponse` streaming contract.

---

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Empty `world_data` or `narrator_persona`**: Handled gracefully; base DM prompt provides complete guidance even when creator fields are empty.
- **Model omits `[MOOD: ...]`**: `extract_mood_tag` cleanly defaults to `mood=None, is_decided=True`, streaming the full text without blocking or raising.
- **Memory Layer abstention**: Omits the `## Grounded World Memory` section cleanly without generating blank headers.
- **Token Overflow Protection**: Even if the model exceeds 150 words, `gemini_max_output_tokens = 350` ensures sentences finish naturally rather than clipping mid-word.

---

## 5. Phased Implementation Tasks
- [ ] **Task 1: Configuration Updates**
  - Update `gemini_temperature = 0.75`, `gemini_max_output_tokens = 350`, `turn_history_window_size = 6` in `apps/turn-resolution-service/app/config.py`.
- [ ] **Task 2: AI Orchestrator Core Refactor**
  - Add `_BASE_DM_SYSTEM_PROMPT` constant.
  - Implement clean helper functions: `_format_world_data`, `_format_facts`, `_format_history`.
  - Refactor `_build_system_instruction` and `_build_master_system_instruction` to incorporate the base prompt.
  - Update `_build_prompt` to generate clean Markdown sections.
  - Integrate mood tag extraction and emission in `_generate_master_mode`.
- [ ] **Task 3: Conformance Testing & Verification**
  - Update unit tests in `tests/turn/steps/test_ai_orchestrator.py`.
  - Run `uv run pytest tests/turn/ -v` to ensure zero regressions across the turn pipeline.
  - Run `uv run ruff format .` and `uv run ruff check . --fix`.
