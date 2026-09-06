// Circle-circle collision helper shared by the player-vs-hazard checks in
// useGameLoop.ts. Pure, no Pixi/DOM dependency — see
// docs/specs/dodge-minigame-design.spec.md §3.4.

export function circlesCollide(
  ax: number,
  ay: number,
  aRadius: number,
  bx: number,
  by: number,
  bRadius: number,
): boolean {
  const dx = ax - bx;
  const dy = ay - by;
  const distanceSquared = dx * dx + dy * dy;
  const radiusSum = aRadius + bRadius;
  return distanceSquared < radiusSum * radiusSum;
}
