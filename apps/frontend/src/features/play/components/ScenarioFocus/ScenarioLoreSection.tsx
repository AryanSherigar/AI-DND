import React from "react";
import { ScenarioDetailResponse } from "../../types/scenario";

interface ScenarioLoreSectionProps {
  scenario: ScenarioDetailResponse;
}

export const ScenarioLoreSection: React.FC<ScenarioLoreSectionProps> = ({
  scenario,
}) => {
  const worldData = scenario.world_data || {};
  const loreText =
    typeof worldData.lore === "string"
      ? worldData.lore
      : typeof worldData.description === "string"
        ? worldData.description
        : scenario.logline ||
          "No detailed backstory has been recorded for this scenario yet. Embark on your playthrough to uncover its mysteries!";

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 md:p-8 shadow-xl backdrop-blur-sm space-y-4">
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
        <span className="text-xl">📜</span>
        <h2 className="font-fell-sc text-2xl font-bold text-amber-200/90 drop-shadow-sm">
          World Lore & Setting
        </h2>
      </div>

      {/* Logline Quote */}
      {scenario.logline && (
        <div className="rounded-xl border-l-4 border-amber-500/80 bg-zinc-950/80 p-4 italic text-zinc-300 font-sans text-base leading-relaxed">
          "{scenario.logline}"
        </div>
      )}

      {/* Longform Lore Body */}
      <div className="text-zinc-300 font-sans text-base leading-relaxed whitespace-pre-line space-y-3">
        {loreText}
      </div>

      {/* Narrator Persona note if present */}
      {scenario.narrator_persona && (
        <div className="mt-4 pt-4 border-t border-zinc-800/80 flex items-start gap-3 text-xs font-mono text-zinc-400">
          <span className="text-emerald-400">🎭 Narrator Tone:</span>
          <span className="text-zinc-300 italic">
            {scenario.narrator_persona}
          </span>
        </div>
      )}
    </div>
  );
};
