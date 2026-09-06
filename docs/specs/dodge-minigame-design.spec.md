# Spec: Dodge Minigame — "Ashfall Dodge" Visual & Gameplay Design

## 1. Objective & User Outcome

- **Problem Statement:** `master-mode-minigames.spec.md` defines the plumbing (trigger, SSE handoff, result submission, state mutation) for the `dodge` minigame type but deliberately leaves its actual gameplay/visual design unspecified, given its outsized importance as a hackathon demo centerpiece. This spec is that design: a self-contained, Undertale-SOUL-box-inspired dodge/survival arena — polished enough to be the single most memorable moment of a demo playthrough, cheap enough to build in the time available.
- **User Story:** As a player, when a minigame triggers, I want a genuinely tense, good-looking few seconds of skill-based dodging — not a placeholder gray box — that clearly communicates my health, the time remaining, and why I won or lost, before control returns to the story.
- **Success Criteria:**
  - Runs entirely client-side (no backend involvement mid-minigame), rendered with PixiJS (WebGL), at a steady 60fps on ordinary laptop hardware.
  - Visually reads as a deliberate genre shift from the "EBook" narration theme — dark, atmospheric, glowing — the instant the overlay opens.
  - Produces exactly one of: `outcome_tag: "win"` (survived the full duration with ≥1 hit point) or `"lose"` (hit points reached 0 before the duration elapsed), plus `score` = hit points remaining at the moment of resolution (`0` on a loss, `1..max_hit_points` on a win) — feeding directly into `master-mode-minigames.spec.md`'s `binary`/`tiered` outcome resolution.
  - Difficulty is entirely determined by the single creator-facing 1-5 slider (`dodge_config.difficulty`) via a fixed preset table — no other creator-facing knobs.
  - Hazards telegraph before becoming dangerous wherever the pattern allows it — hits should read as "I was too slow," never as "that was unfair."
  - Zero new binary/audio asset files: all sound effects are synthesized at runtime via the Web Audio API, keeping the feature dependency-free beyond the `pixi.js` package itself.

## 2. Technical Architecture & Data Flow

- **Components Involved:** `apps/frontend/src/features/play/components/MinigameOverlay/DodgeMinigame/` (new subtree, entirely client-side), the existing `apps/frontend/src/shared/lib/audio/ambient-soundtrack.ts` module (crossfaded into during play, restored on exit), the `pixi.js` npm package (new dependency, `apps/frontend/package.json`).
- **Depends on:** `master-mode-minigames.spec.md`'s `MinigameOverlay.tsx` (mounts this component when `active_minigame.minigame_type === "dodge"`, passing `dodge_config` and an `onComplete(result: MinigameResultPayload)` callback) and `MinigameEventPayload.dodge_config` (`{difficulty: 1-5}`, the only input this subsystem receives from the server).
- **Rendering approach (locked judgment call):** PixiJS is managed **imperatively**, not via a React-reconciled wrapper (e.g. `@pixi/react`) — a single `Application` instance is created in a `useGameLoop` hook on mount and destroyed on unmount, with a `ticker` callback driving the whole simulation (input → movement → hazard spawn/update → collision → hit-point state). This avoids fighting React's render cycle with a 60fps imperative loop and keeps the game's internal state (positions, velocities, spawned-hazard list) out of React state entirely — only the *derived, UI-relevant* values (hit points, time remaining, phase) are pushed into React state, and only when they actually change (once per hit, once per second for the timer), not every frame.
- **Sequence Flow — one dodge encounter:**
  1. `DodgeMinigame.tsx` mounts, reads `dodge_config.difficulty`, looks up the preset in `difficultyPresets.ts`, renders a brief "3…2…1…Go" countdown overlay (CSS/DOM, not Pixi), and crossfades the ambient soundtrack to the `tension` mood track via `ambientSoundtrack.transitionTo("tension")`.
  2. On "Go," `useGameLoop` starts: the PixiJS ticker begins integrating player velocity (from `playerController.ts`, fed by keyboard state + mouse target), spawning hazard waves (from `hazardPatterns.ts`, cycling through the 4 preset patterns), checking circle-circle collisions (`collision.ts`) between the player and every live hazard each frame, and decrementing hit points on an unblocked collision (respecting a brief post-hit invulnerability window).
  3. Each hit: flash/scale-pulse the player sprite, brief arena shake, synthesized hit SFX, HUD hit-point display updates.
  4. Resolution: either `elapsed >= duration` with `hit_points > 0` (win) or `hit_points` reaches `0` (lose, immediate) — a brief impact beat (white flash + short time-scale slowdown), a synthesized win/lose stinger, then `onComplete({ outcome_tag, score: hit_points })` fires and the ambient soundtrack transitions back to whatever mood was active before the minigame started (the overlay/parent is responsible for remembering and restoring it — `DodgeMinigame` only knows "tension," not the pre-minigame mood).
  5. `useGameLoop`'s cleanup (on unmount, which happens the instant `MinigameOverlay` closes on submission) destroys the `Application` and cancels the ticker — no dangling render loop.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Frontend type-check: `npx tsc --noEmit` (from `apps/frontend/`)
- Frontend test: `npx vitest run src/features/play/components/MinigameOverlay/DodgeMinigame`
- Lint/Format: `npx prettier --write . && npx eslint . --fix`
- New dependency: `npm install pixi.js@^8 --workspace apps/frontend` (verify against the actual current PixiJS 8.x release at implementation time; pin an exact version, do not use a floating range in the lockfile).

### 3.2. Testing Strategy & Conformance

- **Location:** `apps/frontend/src/features/play/components/MinigameOverlay/DodgeMinigame/__tests__/`.
- **Mocking:** PixiJS `Application`/WebGL context is not available in the RTL/jsdom test environment — all PixiJS-touching code (`Arena`/scene-graph construction) is excluded from unit tests and covered only by the manual verification pass in §5; everything else in this subtree (`hazardPatterns.ts`, `difficultyPresets.ts`, `collision.ts`, `playerController.ts`) is plain TypeScript with no DOM/Pixi dependency and is fully unit-testable.
- **Required cases:**
  - **`collision.ts`:** two circles whose center distance is less than the sum of radii report a collision; equal to the sum does not (boundary is exclusive, avoids edge-case double-counting).
  - **`difficultyPresets.ts`:** all 5 presets are strictly monotonic in the expected direction (duration non-decreasing, hit_points non-increasing, hazard_speed non-decreasing, hazard_density non-decreasing) from difficulty 1 to 5 — a regression test against accidentally miscalibrating one tier.
  - **`hazardPatterns.ts`:** each of the 4 pattern generators, given a fixed config and elapsed-time sequence, produces spawn events strictly within arena bounds (never spawns a hazard whose initial position is outside the playable area) and respects the configured density (spawn count over a fixed window falls within an expected range, not exact — these are seeded-random generators).
  - **`playerController.ts`:** keyboard-only input (e.g. holding "right") produces a velocity vector pointing purely right at the configured max speed; mouse-only input produces a velocity vector seeking the cursor target, capped at the same max speed; the player's resulting position is clamped to stay within arena bounds even when input would push it outside.
  - **Win/lose/score determination (pure logic extracted from `useGameLoop`, testable independent of the ticker):** `hit_points` reaching 0 before `elapsed >= duration` yields `{outcome_tag: "lose", score: 0}`; `elapsed >= duration` with `hit_points > 0` yields `{outcome_tag: "win", score: hit_points}`.

### 3.3. Project Structure & File Layout

**Files to create:**
- `apps/frontend/src/features/play/components/MinigameOverlay/DodgeMinigame/DodgeMinigame.tsx` — orchestrator component; owns countdown/playing/resolved lifecycle phase, mounts `useGameLoop`, renders `HUD` and the canvas mount point.
- `.../DodgeMinigame/DodgeMinigame.types.ts`
- `.../DodgeMinigame/HUD.tsx` (+ `.types.ts`) — the only actual React-rendered visual component in this subtree (DOM/CSS overlay: hit-point icons, time-remaining bar); reads live values from `useGameLoop`'s return, not from Pixi directly.
- `.../DodgeMinigame/useGameLoop.ts` — owns the PixiJS `Application` lifecycle, the ticker callback, and all per-frame simulation state; exposes `{ phase, hitPoints, timeRemainingMs }` and calls `onComplete` on resolution.
- `.../DodgeMinigame/scene/arena.ts` — builds the arena's static PixiJS scene graph (boundary, background, vignette) and exposes an `updateBoundaryTint(hitPointsFraction)` function for the health-reactive border color.
- `.../DodgeMinigame/scene/player.ts` — builds the player's PixiJS sprite/graphics + glow filter, exposes `updatePosition`/`playHitFlash` functions. (Named `player.ts`, not `Player.tsx` — this is a plain PixiJS scene-graph module, not a React component, per the imperative-rendering decision in §2.)
- `.../DodgeMinigame/scene/hazards.ts` — pools/creates/recycles hazard sprites per pattern type, exposes `spawn`/`updatePositions`/`despawn` functions.
- `.../DodgeMinigame/hazardPatterns.ts` — the 4 pure pattern generators (§3.4).
- `.../DodgeMinigame/difficultyPresets.ts` — the 1-5 preset constant table.
- `.../DodgeMinigame/collision.ts` — circle-circle collision helper.
- `.../DodgeMinigame/playerController.ts` — keyboard + mouse input → velocity vector.
- `.../DodgeMinigame/dodgeAudio.ts` — synthesized SFX (hit/win/lose) via Web Audio oscillators, plus the `ambientSoundtrack.transitionTo("tension")` call and mood-restore on exit.
- `apps/frontend/src/features/play/components/MinigameOverlay/DodgeMinigame/__tests__/{collision,difficultyPresets,hazardPatterns,playerController}.test.ts`

**Files to modify:** none outside this subtree — `MinigameOverlay.tsx` (owned by `master-mode-minigames.spec.md`) only needs to mount `DodgeMinigame` and pass `dodge_config`/`onComplete`, already accounted for there.

### 3.4. Code Style & Interfaces

#### `difficultyPresets.ts`:

```typescript
export interface DodgePreset {
  durationMs: number;
  hitPoints: number;
  hazardSpeedMultiplier: number;
  hazardDensityMultiplier: number;
}

// Difficulty 1 (gentlest) through 5 (hardest). Every field moves
// monotonically harder as difficulty increases — enforced by a unit test.
export const DODGE_DIFFICULTY_PRESETS: Record<number, DodgePreset> = {
  1: { durationMs: 10_000, hitPoints: 5, hazardSpeedMultiplier: 1.0, hazardDensityMultiplier: 0.7 },
  2: { durationMs: 12_000, hitPoints: 4, hazardSpeedMultiplier: 1.15, hazardDensityMultiplier: 0.85 },
  3: { durationMs: 15_000, hitPoints: 3, hazardSpeedMultiplier: 1.3, hazardDensityMultiplier: 1.0 },
  4: { durationMs: 18_000, hitPoints: 3, hazardSpeedMultiplier: 1.5, hazardDensityMultiplier: 1.2 },
  5: { durationMs: 20_000, hitPoints: 2, hazardSpeedMultiplier: 1.75, hazardDensityMultiplier: 1.4 },
};

export const ARENA_WIDTH = 640;
export const ARENA_HEIGHT = 480;
export const PLAYER_RADIUS = 12;
export const PLAYER_MAX_SPEED = 260; // px/sec
export const POST_HIT_INVULNERABILITY_MS = 1000;
export const WAVE_INTERVAL_MS = 3500; // how often a new hazard-pattern wave begins
```

#### `hazardPatterns.ts` — the 4 preset patterns, cycled randomly (no immediate repeat):

```typescript
export type HazardPatternType = "falling_rain" | "converging_ring" | "sweeping_lines" | "homing_orbs";

export interface HazardSpawn {
  id: string;
  shape: "orb" | "shard" | "beam";
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  telegraphMs: number; // time before this hazard becomes collidable/visible-as-dangerous
  homing?: boolean;
}

export interface PatternConfig {
  speedMultiplier: number;
  densityMultiplier: number;
  arenaWidth: number;
  arenaHeight: number;
}

// Each function is a pure generator: given a config and a random seed/source,
// returns the hazards for one wave. No Pixi/DOM dependency — fully unit-testable.
export function generateFallingRain(config: PatternConfig, rng: () => number): HazardSpawn[];
export function generateConvergingRing(config: PatternConfig, rng: () => number): HazardSpawn[];
export function generateSweepingLines(config: PatternConfig, rng: () => number): HazardSpawn[];
export function generateHomingOrbs(config: PatternConfig, rng: () => number): HazardSpawn[];

export const HAZARD_PATTERN_GENERATORS: Record<
  HazardPatternType,
  (config: PatternConfig, rng: () => number) => HazardSpawn[]
> = {
  falling_rain: generateFallingRain,
  converging_ring: generateConvergingRing,
  sweeping_lines: generateSweepingLines,
  homing_orbs: generateHomingOrbs,
};
```

**Pattern behavior (design intent, implemented inside each generator):**
- **Falling Rain:** 4-7 hazards (scaled by density) spawn at random x positions just above the top edge, falling straight down at `hazardSpeedMultiplier`-scaled speed. Shape: small amber teardrop ("shard"). No telegraph needed (approach direction is obvious) — `telegraphMs: 0`.
- **Converging Ring:** 6-10 hazards spawn evenly spaced around a ring just outside the arena boundary, each moving straight toward the arena center at moderate speed. Shape: magenta "orb." `telegraphMs: 300` (brief fade-in before they start moving) so the ring's formation is readable before it closes in.
- **Sweeping Lines:** one thin beam ("beam" shape, full arena width or height) appears with a `telegraphMs: 400` warning flash (low-opacity red) along its final position before becoming solid/collidable for a short window, then despawns. Alternates horizontal/vertical each occurrence. This is the pattern most directly inspired by Undertale's laser-warning telegraphs — fairness comes entirely from the telegraph window.
- **Homing Orbs:** 2-4 orbs ("orb" shape, purple, with a fading trail achieved by drawing 3-4 stale-position ghost sprites at low alpha) spawn at random edge positions and steer toward the player's *current* position each frame, but with a capped turn rate (never a full snap-to-player vector) so they are always out-runnable with clean movement — never a guaranteed hit.

Waves alternate pattern types via a simple "don't repeat the last one" random pick every `WAVE_INTERVAL_MS`, continuing until `durationMs` elapses or the player loses.

#### `collision.ts`:

```typescript
export function circlesCollide(
  ax: number, ay: number, aRadius: number,
  bx: number, by: number, bRadius: number,
): boolean {
  const dx = ax - bx;
  const dy = ay - by;
  const distanceSquared = dx * dx + dy * dy;
  const radiusSum = aRadius + bRadius;
  return distanceSquared < radiusSum * radiusSum;
}
```

#### `playerController.ts`:

```typescript
export interface PlayerControllerState {
  keysDown: Set<string>; // "ArrowUp"|"ArrowDown"|"ArrowLeft"|"ArrowRight"|"w"|"a"|"s"|"d"
  mouseTarget: { x: number; y: number } | null; // set on mousemove within the arena
}

// Keyboard sets a normalized (diagonal-safe) velocity directly. If a mouse
// target is also present, it's blended in as a secondary seek vector so
// either input method alone is fully sufficient, and using both doesn't
// fight itself. Output is clamped so the player's next position stays
// within [PLAYER_RADIUS, arenaWidth - PLAYER_RADIUS] (and same for y).
export function computeVelocity(
  state: PlayerControllerState,
  currentX: number,
  currentY: number,
  maxSpeed: number,
): { vx: number; vy: number };

export function clampToArena(
  x: number, y: number, radius: number, arenaWidth: number, arenaHeight: number,
): { x: number; y: number };
```

#### `dodgeAudio.ts` — synthesized SFX, no asset files:

```typescript
// Short Web Audio oscillator-based blips — no audio files needed.
// hit: a brief low square-wave thud. win: a short ascending 3-note
// arpeggio. lose: a short descending tone. All fire-and-forget, sharing
// one AudioContext with (or independent of) ambient-soundtrack.ts.
export function playHitSfx(): void;
export function playWinStinger(): void;
export function playLoseStinger(): void;

// Crossfades the existing ambient mood track to "tension" on minigame
// start, and restores the previously-active mood on exit — thin wrapper
// around apps/frontend/src/shared/lib/audio/ambient-soundtrack.ts's
// existing transitionTo(mood) API. This module does not manage mood
// state itself; it just remembers what to restore to.
export function enterMinigameAudio(): () => void; // returns a restore function
```

#### Visual language (art direction, not code):

- **Palette:** near-black arena background (`#0a0a14`) with a soft radial vignette toward the edges; a thin, rounded-rect arena border that glows cool blue-white (`#7ec8ff`) at full health and interpolates toward amber/red (`#ff6b4a`) as `hitPoints` drops — continuous tint interpolation driven by `arena.ts`'s `updateBoundaryTint(hitPointsFraction)`, not a hard threshold snap.
- **Player:** a small glowing orb, cool white/cyan (`#e8f6ff` core, `#7ec8ff` glow via a Pixi blur/glow filter), radius `PLAYER_RADIUS`. On a hit: scale-pulses briefly (e.g. 1.0 → 1.4 → 1.0 over ~200ms), flashes white/red, and the whole arena container jitters (±4px random offset) for ~150ms. During the post-hit invulnerability window, alpha blinks at roughly 10Hz.
- **Hazards:** color-coded per pattern for instant readability (amber "falling rain" shards, magenta "converging ring" orbs, red-flash "sweeping lines" beams, purple-trailed "homing orbs") — a player should be able to tell what kind of threat is on screen at a glance, purely from color/shape, without reading anything.
- **HUD:** minimal and unobtrusive — hit points as small glowing ember/dot icons along the top-left (filled vs. dimmed for lost), a thin horizontal time-remaining bar along the very top edge of the arena, colored to match the current boundary tint.
- **Resolution beat:** on the deciding hit or the final tick of survival, a brief full-canvas white flash plus a short time-scale slowdown (ticker's delta multiplier drops to ~0.3 for ~500ms) before the overlay closes — a clear, satisfying "moment" rather than an abrupt cutoff.

### 3.5. Git & Review Workflow

- Branch: same `feat/master-mode-minigames` branch as the system spec, or a stacked `feat/dodge-minigame` branch if implemented by a separate subagent pass — either is fine since this subtree has no other in-progress consumers.
- Commit scope: one commit adding the `pixi.js` dependency, one for the pure/testable modules (`collision.ts`, `playerController.ts`, `difficultyPresets.ts`, `hazardPatterns.ts`) with their tests, one for the PixiJS scene modules (`arena.ts`, `player.ts`, `hazards.ts`), one for `useGameLoop.ts` + `DodgeMinigame.tsx` + `HUD.tsx` wiring it all together, one for `dodgeAudio.ts`.
- PR checklist: all four pure-logic unit test files pass; manual playtest at every difficulty level (1 and 5 at minimum) confirms the game is beatable-with-skill at max difficulty and trivially easy at difficulty 1; confirm no PixiJS `Application` instance leaks across repeated trigger→resolve→trigger cycles (destroy is actually called).

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** clamp player position to arena bounds every frame; respect post-hit invulnerability (never double-count the same hazard's collision across consecutive frames); destroy the PixiJS `Application` on unmount; restore the pre-minigame ambient mood on exit.
- ⚠️ **Ask First:** adding a 5th hazard pattern or creator-authorable pattern scripting — both are explicit locked-scope boundaries from the product decision (3-4 preset patterns, not creator-scriptable), not implementation details.
- 🚫 **Never:** let `useGameLoop` make any network call or reference `play.store.ts`/SSE directly (it only receives `dodge_config` as props and calls `onComplete` — the overlay/store integration is entirely `MinigameOverlay`'s responsibility, keeping this subtree fully self-contained and reusable/testable in isolation); let a hazard spawn fully outside the arena bounds; let the game continue running (ticker still active) after `onComplete` has fired.

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **Tab loses focus mid-minigame (keys stuck "down"):** `playerController.ts`'s `keysDown` set must be cleared on a `window.blur` event, not just `keyup` — otherwise a player who alt-tabs mid-game returns to a phantom held direction.
- **Extremely fast machine / very slow machine:** the ticker uses PixiJS's built-in delta-time scaling for all movement/spawn-timing math (never a fixed per-frame step), so gameplay speed is consistent regardless of actual frame rate; verify this explicitly during implementation rather than assuming Pixi's default ticker behavior is sufficient.
- **Player resizes the browser window mid-minigame:** the arena is a fixed logical size (`ARENA_WIDTH`/`ARENA_HEIGHT`) rendered into a responsively-scaled canvas (CSS scale-to-fit, not a resized Pixi renderer) — simplest correct approach, avoids re-deriving all positions on resize.
- **Player wins/loses simultaneously (last hazard's hit brings hit_points to 0 on the exact frame `elapsed` crosses `durationMs`):** loss takes precedence — `hit_points <= 0` is checked before the duration check each tick, so simultaneous resolution always reads as a loss, never an ambiguous double-fire of `onComplete`.
- **Reload mid-minigame (per the system spec's resume design):** `DodgeMinigame` has no server-persisted mid-game state — a resumed session simply restarts the encounter fresh from the countdown, using the same `dodge_config` from `_pending_minigame`. This is an accepted simplification: the alternative (serializing hazard positions/velocities server-side) is out of scope.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Dependency + pure modules):** Add `pixi.js`; implement `difficultyPresets.ts`, `collision.ts`, `playerController.ts`, `hazardPatterns.ts` with their unit tests. Verify: `npx vitest run src/features/play/components/MinigameOverlay/DodgeMinigame/__tests__`.
- [ ] **Task 2 (Scene modules):** Implement `scene/arena.ts`, `scene/player.ts`, `scene/hazards.ts`. Verify: manual — mount in isolation (e.g. a throwaway dev route) and confirm the arena/player/a hardcoded hazard render correctly.
- [ ] **Task 3 (Game loop + orchestration):** Implement `useGameLoop.ts`, `DodgeMinigame.tsx`, `HUD.tsx`. Verify: manual playtest of a full encounter at difficulty 3, confirming win and lose paths both resolve correctly with the right `score`.
- [ ] **Task 4 (Audio):** Implement `dodgeAudio.ts`; wire the tension-mood crossfade in and the prior-mood restore out. Verify: manual — confirm hit/win/lose SFX play, and ambient music correctly returns to its pre-minigame mood after the overlay closes.
- [ ] **Task 5 (Difficulty pass):** Manually playtest all 5 difficulty levels; adjust `difficultyPresets.ts` constants if 1 isn't trivially easy or 5 isn't genuinely challenging-but-fair. Verify: the monotonicity unit test still passes after any tuning.
- [ ] **Task 6 (Polish pass):** Confirm the hit-flash/shake/invulnerability-blink, boundary tint interpolation, and win/lose resolution-beat all read clearly at normal playback speed, not just in slow-motion code review. This is the task most worth a second pair of eyes given the demo stakes.
