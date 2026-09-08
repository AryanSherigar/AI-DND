import { HUDProps } from "./HUD.types";

/**
 * Minimal, unobtrusive overlay: hit-point dots top-left, a thin
 * time-remaining bar along the top edge. Pure DOM/Tailwind, reads only the
 * live values useGameLoop already derived — no PixiJS/game-state knowledge
 * of its own. See docs/specs/dodge-minigame-design.spec.md §3.4.
 */
export function HUD({
  hitPoints,
  maxHitPoints,
  timeRemainingMs,
  durationMs,
}: HUDProps) {
  const timeFraction =
    durationMs > 0 ? Math.max(0, timeRemainingMs / durationMs) : 0;

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col gap-2 p-3">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-sky-300 transition-[width] duration-150 ease-linear"
          style={{ width: `${timeFraction * 100}%` }}
        />
      </div>
      <div className="flex gap-1.5">
        {Array.from({ length: maxHitPoints }, (_, index) => (
          <span
            key={index}
            className={
              index < hitPoints
                ? "h-3 w-3 rounded-full bg-sky-300 shadow-[0_0_6px_2px_rgba(126,200,255,0.6)]"
                : "h-3 w-3 rounded-full bg-white/10"
            }
          />
        ))}
      </div>
    </div>
  );
}
