// Keyboard (arrow keys + WASD) + mouse-follow input → clamped velocity
// vector. Pure computation (computeVelocity/clampToArena) has no DOM
// dependency and is unit-tested directly; attachPlayerControls wires real
// DOM listeners for useGameLoop.ts to consume.
// See docs/specs/dodge-minigame-design.spec.md §3.4 and §4 (window.blur).

const MOUSE_SEEK_DEADZONE_PX = 2;

export interface PlayerControllerState {
  keysDown: Set<string>; // "ArrowUp"|"ArrowDown"|"ArrowLeft"|"ArrowRight"|"w"|"a"|"s"|"d"
  mouseTarget: { x: number; y: number } | null; // set on mousemove within the arena
}

interface Vector2 {
  x: number;
  y: number;
}

const KEY_DIRECTIONS: Record<string, Vector2> = {
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
  w: { x: 0, y: -1 },
  s: { x: 0, y: 1 },
  a: { x: -1, y: 0 },
  d: { x: 1, y: 0 },
};

export function createPlayerControllerState(): PlayerControllerState {
  return { keysDown: new Set<string>(), mouseTarget: null };
}

function normalize(vector: Vector2): Vector2 {
  const magnitude = Math.hypot(vector.x, vector.y);
  if (magnitude === 0) return { x: 0, y: 0 };
  return { x: vector.x / magnitude, y: vector.y / magnitude };
}

function scaleToMax(
  vector: Vector2,
  maxSpeed: number,
): { vx: number; vy: number } {
  const unit = normalize(vector);
  return { vx: unit.x * maxSpeed, vy: unit.y * maxSpeed };
}

function computeKeyboardVector(keysDown: Set<string>): Vector2 {
  let x = 0;
  let y = 0;
  for (const key of keysDown) {
    const direction = KEY_DIRECTIONS[key];
    if (!direction) continue;
    x += direction.x;
    y += direction.y;
  }
  return normalize({ x, y });
}

function computeMouseSeekVector(
  mouseTarget: { x: number; y: number } | null,
  currentX: number,
  currentY: number,
): Vector2 {
  if (!mouseTarget) return { x: 0, y: 0 };
  const dx = mouseTarget.x - currentX;
  const dy = mouseTarget.y - currentY;
  if (Math.hypot(dx, dy) < MOUSE_SEEK_DEADZONE_PX) return { x: 0, y: 0 };
  return normalize({ x: dx, y: dy });
}

// Keyboard sets a normalized (diagonal-safe) velocity directly. If a mouse
// target is also present, it's blended in as a secondary seek vector so
// either input method alone is fully sufficient, and using both doesn't
// fight itself.
export function computeVelocity(
  state: PlayerControllerState,
  currentX: number,
  currentY: number,
  maxSpeed: number,
): { vx: number; vy: number } {
  const keyboardVector = computeKeyboardVector(state.keysDown);
  const isKeyboardActive = keyboardVector.x !== 0 || keyboardVector.y !== 0;

  if (!isKeyboardActive) {
    const mouseVector = computeMouseSeekVector(
      state.mouseTarget,
      currentX,
      currentY,
    );
    return scaleToMax(mouseVector, maxSpeed);
  }

  if (!state.mouseTarget) {
    return scaleToMax(keyboardVector, maxSpeed);
  }

  const mouseVector = computeMouseSeekVector(
    state.mouseTarget,
    currentX,
    currentY,
  );
  const blended: Vector2 = {
    x: keyboardVector.x + mouseVector.x,
    y: keyboardVector.y + mouseVector.y,
  };
  return scaleToMax(blended, maxSpeed);
}

// Output is clamped so the player's next position stays within
// [radius, arenaWidth - radius] (and the same for y).
export function clampToArena(
  x: number,
  y: number,
  radius: number,
  arenaWidth: number,
  arenaHeight: number,
): { x: number; y: number } {
  return {
    x: Math.min(arenaWidth - radius, Math.max(radius, x)),
    y: Math.min(arenaHeight - radius, Math.max(radius, y)),
  };
}

function toStateKey(event: KeyboardEvent): string | null {
  if (KEY_DIRECTIONS[event.key]) return event.key;
  const lowerKey = event.key.toLowerCase();
  if (KEY_DIRECTIONS[lowerKey]) return lowerKey;
  return null;
}

// Wires real keyboard/mouse DOM listeners into a PlayerControllerState.
// Clears keysDown on window.blur (not just keyup) so an alt-tab mid-game
// never leaves a phantom held direction — see design spec §4.
//
// mouseSurface is the CSS-scaled canvas mount element; arenaWidth/
// arenaHeight are the fixed *logical* arena dimensions (ARENA_WIDTH /
// ARENA_HEIGHT). Mapping through the [0,1] fraction of the surface's
// rendered bounds (not its clientWidth/clientHeight) keeps mouse targets
// correct regardless of the CSS scale-to-fit factor — see design spec §4's
// "player resizes the browser window mid-minigame" edge case.
export function attachPlayerControls(
  state: PlayerControllerState,
  mouseSurface: HTMLElement,
  arenaWidth: number,
  arenaHeight: number,
): () => void {
  const handleKeyDown = (event: KeyboardEvent): void => {
    const key = toStateKey(event);
    if (key) state.keysDown.add(key);
  };
  const handleKeyUp = (event: KeyboardEvent): void => {
    const key = toStateKey(event);
    if (key) state.keysDown.delete(key);
  };
  const handleBlur = (): void => {
    state.keysDown.clear();
  };
  const handleMouseMove = (event: MouseEvent): void => {
    const bounds = mouseSurface.getBoundingClientRect();
    if (bounds.width === 0 || bounds.height === 0) return;
    state.mouseTarget = {
      x: ((event.clientX - bounds.left) / bounds.width) * arenaWidth,
      y: ((event.clientY - bounds.top) / bounds.height) * arenaHeight,
    };
  };
  const handleMouseLeave = (): void => {
    state.mouseTarget = null;
  };

  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("keyup", handleKeyUp);
  window.addEventListener("blur", handleBlur);
  mouseSurface.addEventListener("mousemove", handleMouseMove);
  mouseSurface.addEventListener("mouseleave", handleMouseLeave);

  return () => {
    window.removeEventListener("keydown", handleKeyDown);
    window.removeEventListener("keyup", handleKeyUp);
    window.removeEventListener("blur", handleBlur);
    mouseSurface.removeEventListener("mousemove", handleMouseMove);
    mouseSurface.removeEventListener("mouseleave", handleMouseLeave);
  };
}
