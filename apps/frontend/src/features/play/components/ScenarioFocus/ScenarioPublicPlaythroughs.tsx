import React from "react";
import { PublicPlaythroughSummary } from "../../types/scenario";

interface ScenarioPublicPlaythroughsProps {
  playthroughs: PublicPlaythroughSummary[];
}

export const ScenarioPublicPlaythroughs: React.FC<
  ScenarioPublicPlaythroughsProps
> = ({ playthroughs }) => {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 md:p-8 shadow-xl space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">🗡️</span>
          <h2 className="font-fell-sc text-2xl font-bold text-amber-200/90">
            Active & Completed Playthroughs
          </h2>
        </div>
        <span className="font-mono text-xs text-zinc-400 bg-zinc-950 border border-zinc-800 px-2.5 py-1 rounded-md">
          {playthroughs.length} Public Runs
        </span>
      </div>

      {playthroughs.length === 0 ? (
        <div className="p-6 text-center font-mono text-sm text-zinc-500">
          No public playthroughs recorded for this scenario yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {playthroughs.map((pt) => (
            <div
              key={pt.playthrough_id}
              className="flex items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-950/60 p-3.5 font-mono text-xs"
            >
              <div className="space-y-1">
                <div className="font-bold text-zinc-200">
                  {pt.character_name || "Unknown Adventurer"}
                </div>
                <div className="text-zinc-500">Player: {pt.player_name}</div>
              </div>

              <div className="flex flex-col items-end gap-1">
                <span className="rounded bg-zinc-900 border border-zinc-800 px-2 py-0.5 text-zinc-300">
                  Turn {pt.turn_count}
                </span>
                <span
                  className={`capitalize ${
                    pt.status === "completed"
                      ? "text-emerald-400 font-semibold"
                      : "text-amber-400"
                  }`}
                >
                  {pt.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
