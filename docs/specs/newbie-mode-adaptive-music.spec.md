# Spec: Newbie Mode Adaptive Music System

## 1. Objective & User Outcome
- **Problem Statement:** Gameplay in AI-DND is currently a silent reading experience. As dramatic events, sudden dangers, or quiet discoveries occur during the narrative, there is no musical atmosphere to reinforce narrative pacing, emotional tension, or player immersion.
- **User Story:** As a player playing a newbie scenario, I want evocative background music that smoothly shifts its mood (e.g. from calm exploration to intense combat or eerie mystery) based on what is happening in the narrative, so that my roleplay experience feels cinematic, atmospheric, and emotionally resonant without jarring abrupt track cuts or annoying repetitive switches.
- **Success Criteria:**
  - Turn Resolution Service (TRS) classifies and emits a lightweight `mood` SSE event at the start of each turn resolution.
  - Gemini outputs an opening mood tag (e.g. `[MOOD: tension]`), which TRS strips cleanly from the player's narration stream with zero leakage.
  - TRS parser gracefully tolerates missing tags, lowercase variations, or whitespace variations, falling back to the scenario's prior or default mood without throwing errors or dropping narration words.
  - Frontend Web Audio API crossfades seamlessly between mood tracks using a 4-second exponential gain curve.
  - Dual-layer stabilization prevents music thrashing: server-side prompt instructions preserve mood across minor actions, and client-side cooldown (45 seconds / 2 turns) suppresses non-combat mood oscillation.
  - Audio starts unmuted upon the player's first interaction, respecting browser autoplay policies, with header volume/mute controls and `localStorage` persistence.
  - Spectator SSE stream receives synchronized `mood` events so spectating players hear matching adaptive music.

---

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **Gemini (Vertex AI):** System instruction prompts model to classify scene tone into one of 5 canonical moods (`peaceful`, `mystery`, `tension`, `combat`, `melancholy`) and output `[MOOD: <tag>]` on the first line.
  - **Turn Resolution Service (FastAPI / SSE):**
    - `turn/steps/ai_orchestrator.py`: Stream parser inspects the initial tokens, extracts & normalizes the mood tag, and emits an SSE `mood` event before yielding narration tokens.
    - `turn/pipeline.py`: Sequences the `mood` event to the active player SSE stream and relays to `spectator_manager`.
    - `turn/steps/response_streamer.py`: Formats the `mood` SSE event: `event: mood\ndata: <tag>`.
  - **Frontend (React + Vite + TypeScript):**
    - `shared/lib/audio/ambient-soundtrack.ts`: Web Audio API manager with dual `AudioNode` gain channels for 4-second exponential crossfading, looping, and master volume control.
    - `features/play/stores/play.store.ts`: Client state for active mood, muted state, volume level, and anti-thrashing cooldown timers.
    - `features/play/components/PlayScreen/EBook/EBookHeader.tsx`: Ambient music control button with mute toggle and volume slider popover.
    - `public/audio/moods/`: Static looped audio assets for `peaceful.mp3`, `mystery.mp3`, `tension.mp3`, `combat.mp3`, and `melancholy.mp3`.

- **Sequence Flow:**
  ```mermaid
  sequenceDiagram
    autonumber
    actor Player
    participant UI as NewbiePlayScreen (EBook)
    participant AudioEngine as AmbientSoundtrack (Web Audio)
    participant TRS as Turn Resolution Service
    participant Gemini as Gemini (Vertex AI)
    participant Spectator as Spectator SSE Client

    Player->>UI: Submits Turn Action ("I draw my sword and enter the crypt")
    UI->>TRS: POST /v1/turn (SSE)
    TRS->>Gemini: Stream Narration (System instruction requests [MOOD: <tag>])
    Gemini-->>TRS: First chunk: "[MOOD: tension]\nThe crypt gates groan..."
    TRS->>TRS: Extract & validate tag "tension", strip tag from narration buffer
    TRS-->>UI: SSE event: mood (data: "tension")
    TRS-->>Spectator: SpectatorManager relay: mood "tension"
    UI->>AudioEngine: Transition to "tension"
    AudioEngine->>AudioEngine: 4s exponential crossfade (Previous Track -> Tension Track)
    loop Narration Chunks
      Gemini-->>TRS: "The crypt gates groan open into pitch darkness..."
      TRS-->>UI: SSE event: narration
      TRS-->>Spectator: SpectatorManager relay: narration
    end
    TRS-->>UI: SSE event: done
  ```

---

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Core API & TRS Lint / Format:**
  `ruff format . && ruff check . --fix`
- **TRS Unit & Integration Tests:**
  `pytest apps/turn-resolution-service/tests/turn/test_pipeline.py apps/turn-resolution-service/tests/turn/test_ai_orchestrator.py -v`
- **Frontend Lint & Type-Check:**
  `cd apps/frontend && npm run lint && npx tsc --noEmit`
- **Frontend Unit Tests:**
  `cd apps/frontend && npm run test`

### 3.2. Testing Strategy & Conformance
- **TRS Backend Unit Tests (`tests/turn/test_ai_orchestrator.py` & `test_mood.py`):**
  - Verify exact tag extraction: `[MOOD: combat]\n` stripped; yields `combat` mood event, followed by clean narration chunks.
  - Case-insensitivity & whitespace tolerance: `[mood: tension ]` normalized to `tension`.
  - Missing tag tolerance: Gemini output with no tag streams all text completely with no dropped characters, emitting default/previous mood.
  - Invalid mood hallucination: `[MOOD: spooky]` falls back to `mystery` or previous mood without error.
  - Multi-chunk fragmentation: Tag split across two streaming chunks (e.g. `[MOOD:` in chunk 1, ` combat]\n` in chunk 2) is correctly buffered and reassembled.
- **Frontend Audio Engine Tests (`apps/frontend/src/shared/lib/audio/__tests__/ambient-soundtrack.test.ts`):**
  - Mocks `AudioContext` and verifies crossfade gain scheduling: `gainNode.gain.setValueAtTime` and `exponentialRampToValueAtTime`.
  - Verifies anti-thrashing cooldown: non-combat mood change requested within 45 seconds of last transition is debounced/ignored; combat mood triggers immediately.
  - Verifies `localStorage` persistence for volume level and muted flag.
  - Verifies mute/unmute transitions without audio clipping.

### 3.3. Project Structure & File Layout
- **Files to Create:**
  - `apps/turn-resolution-service/app/turn/mood.py`: Canonical mood constants, synonym normalization dictionary, and tag parsing helpers.
  - `apps/turn-resolution-service/tests/turn/test_mood.py`: Deterministic test suite for mood parsing and fallbacks.
  - `apps/frontend/src/shared/lib/audio/ambient-soundtrack.ts`: Web Audio API sound controller with dual gain-node crossfading and loop management.
  - `apps/frontend/src/shared/lib/audio/__tests__/ambient-soundtrack.test.ts`: Unit tests for audio transitions and cooldown logic.
  - `apps/frontend/src/features/play/components/PlayScreen/EBook/EBookAudioControl.tsx`: Audio volume popover and mute toggle button.
  - `apps/frontend/public/audio/moods/`: Directory containing ambient loop audio files (`peaceful.mp3`, `mystery.mp3`, `tension.mp3`, `combat.mp3`, `melancholy.mp3`).
  - `scripts/generate_ambient_audio.py`: Standalone synthesis script creating harmonious looping MP3/OGG ambient audio assets.
- **Files to Modify:**
  - `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py`: Update prompt instructions to request mood tag; buffer initial chunk to extract tag cleanly.
  - `apps/turn-resolution-service/app/turn/steps/response_streamer.py`: Add `mood_event(mood: str) -> ServerSentEvent`.
  - `apps/turn-resolution-service/app/turn/pipeline.py`: Emit `mood` event over SSE and publish to `spectator_manager`.
  - `apps/frontend/src/features/play/stores/play.store.ts`: Listen for SSE `mood` events, maintain active mood and audio cooldown state, and invoke crossfader.
  - `apps/frontend/src/features/play/components/PlayScreen/EBook/EBookHeader.tsx`: Embed `EBookAudioControl`.

### 3.4. Code Style & Interfaces
- **TRS Canonical Types (`apps/turn-resolution-service/app/turn/mood.py`):**
  ```python
  from enum import StrEnum

  class MoodTag(StrEnum):
      PEACEFUL = "peaceful"
      MYSTERY = "mystery"
      TENSION = "tension"
      COMBAT = "combat"
      MELANCHOLY = "melancholy"

  CANONICAL_MOODS: set[str] = {m.value for m in MoodTag}

  MOOD_SYNONYMS: dict[str, MoodTag] = {
      "calm": MoodTag.PEACEFUL,
      "exploration": MoodTag.PEACEFUL,
      "serene": MoodTag.PEACEFUL,
      "eerie": MoodTag.MYSTERY,
      "suspense": MoodTag.TENSION,
      "danger": MoodTag.TENSION,
      "action": MoodTag.COMBAT,
      "battle": MoodTag.COMBAT,
      "sorrow": MoodTag.MELANCHOLY,
      "sad": MoodTag.MELANCHOLY,
      "grief": MoodTag.MELANCHOLY,
  }
  ```

- **Frontend TypeScript Interfaces (`apps/frontend/src/features/play/types/audio.types.ts`):**
  ```typescript
  export type ScenarioMood =
    | "peaceful"
    | "mystery"
    | "tension"
    | "combat"
    | "melancholy";

  export interface AudioSettings {
    is_muted: boolean;
    volume: number; // 0.0 to 1.0
  }

  export interface MoodAudioConfig {
    mood: ScenarioMood;
    src: string;
    label: string;
    crossfade_duration_seconds: number;
  }
  ```

### 3.5. Git & Review Workflow
- **Branch:** `feat/newbie-adaptive-music`
- **Commit Scope:** `feat(music): add newbie mode adaptive ambient soundtrack`
- **PR Validation Checklist:**
  - [ ] `ruff format` and `ruff check` pass with zero warnings.
  - [ ] All functions under 30 lines and nesting depth <= 2.
  - [ ] Type hints on all new Python functions; TypeScript strict mode compliant.
  - [ ] SSE `mood` event tested and covered in `tests/turn/test_pipeline.py`.
  - [ ] Narration stream emits without leaking `[MOOD: ...]` bracketed text.
  - [ ] Web Audio crossfading smooth without audible clipping or errors in unmuted/muted states.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:**
  - Check browser user interaction state before calling `audioContext.resume()`.
  - Fall back gracefully to `peaceful` or current mood if model does not supply a mood tag.
  - Ensure zero narration tokens are dropped even when tag buffering is used.
- ⚠️ **Ask First:**
  - Modifying DB migrations (decided: store optional initial mood in `Scenario.world_data["initial_mood"]`, no migration required).
  - Adding heavy external client audio npm packages (decided: use lightweight native Web Audio API with zero external dependencies).
- 🚫 **Never:**
  - Block or buffer the entire narration stream waiting for mood classification.
  - Emit bare unhandled browser audio exceptions to console when autoplay is blocked.
  - Add intrusive audio without a player-accessible mute toggle.

---

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Autoplay Restriction:** Modern browsers reject `AudioContext.resume()` or audio playback if triggered before user gesture. The audio controller remains in a suspended/standby state and seamlessly attaches a one-time document click/touch/keydown listener to unlock the `AudioContext` on first interaction.
- **Malformed or Missing Mood Tag:** If Gemini omits the tag or prefixes narration with conversational text, the parser flushes the buffer as narration within 100 characters, retaining the currently active mood.
- **Audio File Load Failure (Network Drop / 404):** If an MP3 audio asset fails to load over the network, `ambient-soundtrack.ts` catches the `error` event, logs a debug warning, and falls back to a silent state without throwing an uncaught exception or disrupting gameplay.
- **Stream Interruption / Degraded Turn:** If turn generation fails or triggers a `degraded` SSE event, the current soundtrack continues looping normally; it does not cut out abruptly.
- **Rapid Actions / Anti-Thrashing:** If a player submits actions rapidly, transitions are throttled by a 45-second / 2-turn cooldown (unless transitioning to `combat`, which immediately takes priority to heighten urgency).

---

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Audio Assets & Synthesis):**
  - Create audio asset generation script `scripts/generate_ambient_audio.py`.
  - Generate clean, loopable MP3/OGG audio files for the 5 moods in `apps/frontend/public/audio/moods/`.
- [ ] **Task 2 (TRS Mood Extraction & Normalization):**
  - Implement `app/turn/mood.py` with mood enums, synonyms, and stream tag extractor.
  - Add unit tests in `apps/turn-resolution-service/tests/turn/test_mood.py`.
- [ ] **Task 3 (TRS Pipeline Integration & SSE Streaming):**
  - Update `app/turn/steps/ai_orchestrator.py` to prompt Gemini for mood and extract the tag.
  - Add `mood_event` in `app/turn/steps/response_streamer.py`.
  - Update `app/turn/pipeline.py` to emit `mood` SSE events and publish to `spectator_manager`.
  - Add integration tests in `apps/turn-resolution-service/tests/turn/test_pipeline.py`.
- [ ] **Task 4 (Frontend Web Audio Controller & Store Integration):**
  - Implement `apps/frontend/src/shared/lib/audio/ambient-soundtrack.ts` with 4s exponential crossfading and autoplay unlock.
  - Update `apps/frontend/src/features/play/stores/play.store.ts` to receive `mood` events, manage cooldowns, and drive audio.
  - Add unit tests for the audio controller in `apps/frontend/src/shared/lib/audio/__tests__/ambient-soundtrack.test.ts`.
- [ ] **Task 5 (Frontend UI Controls in EBook View):**
  - Implement `EBookAudioControl.tsx` with mute toggle and volume slider.
  - Integrate `EBookAudioControl` into `EBookHeader.tsx`.
- [ ] **Task 6 (Verification & Conformance):**
  - Run TRS test suite: `pytest apps/turn-resolution-service/tests`.
  - Run frontend lint, typecheck, and tests: `npm run lint`, `npx tsc --noEmit`, `npm run test`.
