// WASD keyboard input → clamped velocity vector. Pure computation
// (computeVelocity/clampToArena) has no DOM dependency; attachPlayerControls
// wires a focusable arena and blur cleanup for useGameLoop.ts.

export interface PlayerControllerState {
  keysDown: Set<string>; // "w"|"a"|"s"|"d"
}

interface Vector2 {
  x: number;
  y: number;
}

const KEY_DIRECTIONS: Record<string, Vector2> = {
  w: { x: 0, y: -1 },
  s: { x: 0, y: 1 },
  a: { x: -1, y: 0 },
  d: { x: 1, y: 0 },
};

export function createPlayerControllerState(): PlayerControllerState {
  return { keysDown: new Set<string>() };
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

export function computeVelocity(
  state: PlayerControllerState,
  _currentX: number,
  _currentY: number,
  maxSpeed: number,
): { vx: number; vy: number } {
  const keyboardVector = computeKeyboardVector(state.keysDown);
  return scaleToMax(keyboardVector, maxSpeed);
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

// Wires keyboard DOM listeners into a PlayerControllerState.
// Clears keysDown on window.blur (not just keyup) so an alt-tab mid-game
// never leaves a phantom held direction — see design spec §4.
//
export function attachPlayerControls(
  state: PlayerControllerState,
  keyboardSurface: HTMLElement,
  onBlur?: () => void,
): () => void {
  const handleKeyDown = (event: KeyboardEvent): void => {
    const key = toStateKey(event);
    if (key) {
      event.preventDefault();
      state.keysDown.add(key);
    }
  };
  const handleKeyUp = (event: KeyboardEvent): void => {
    const key = toStateKey(event);
    if (key) {
      event.preventDefault();
      state.keysDown.delete(key);
    }
  };
  const handleBlur = (): void => {
    state.keysDown.clear();
    onBlur?.();
  };

  keyboardSurface.addEventListener("keydown", handleKeyDown);
  keyboardSurface.addEventListener("keyup", handleKeyUp);
  window.addEventListener("blur", handleBlur);

  return () => {
    keyboardSurface.removeEventListener("keydown", handleKeyDown);
    keyboardSurface.removeEventListener("keyup", handleKeyUp);
    window.removeEventListener("blur", handleBlur);
  };
}
