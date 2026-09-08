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

/** True when a player circle overlaps an arena-spanning beam.
 * `isHorizontal` describes a beam spanning left-to-right at `beamY`; otherwise
 * it spans top-to-bottom at `beamX`. Keeping this separate from circle
 * collision is important: a beam's centre is not its only dangerous point.
 */
export function circleIntersectsBeam(
  playerX: number,
  playerY: number,
  playerRadius: number,
  beamX: number,
  beamY: number,
  halfThickness: number,
  isHorizontal: boolean,
): boolean {
  const perpendicularDistance = isHorizontal
    ? Math.abs(playerY - beamY)
    : Math.abs(playerX - beamX);
  return perpendicularDistance < playerRadius + halfThickness;
}

/** Collision gate used by the loop: telegraphs are always non-damaging. */
export function hazardCollidesWithPlayer(
  playerX: number,
  playerY: number,
  playerRadius: number,
  hazard: {
    isTelegraphing: boolean;
    shape: "orb" | "shard" | "beam";
    x: number;
    y: number;
    radius: number;
  },
  arenaWidth: number,
): boolean {
  if (hazard.isTelegraphing) return false;
  return hazard.shape === "beam"
    ? circleIntersectsBeam(
        playerX,
        playerY,
        playerRadius,
        hazard.x,
        hazard.y,
        hazard.radius,
        hazard.x === arenaWidth / 2,
      )
    : circlesCollide(
        playerX,
        playerY,
        playerRadius,
        hazard.x,
        hazard.y,
        hazard.radius,
      );
}
