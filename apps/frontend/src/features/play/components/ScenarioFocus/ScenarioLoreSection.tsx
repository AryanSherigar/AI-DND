import React from "react";
import { ScenarioDetailResponse } from "../../types/scenario";
import { SectionHeading } from "./SectionHeading";

interface ScenarioLoreSectionProps {
  scenario: ScenarioDetailResponse;
}

const extractLoreText = (
  worldData: Record<string, unknown>,
  defaultLogline?: string | null,
): string => {
  if (typeof worldData.lore === "string") return worldData.lore;
  if (typeof worldData.description === "string") return worldData.description;
  return defaultLogline || "";
};

export const ScenarioLoreSection: React.FC<ScenarioLoreSectionProps> = ({
  scenario,
}) => {
  const worldData = (scenario.world_data || {}) as Record<string, unknown>;
  const loreText = extractLoreText(worldData, scenario.logline);

  return (
    <section>
      <SectionHeading label="About" />

      {scenario.logline && (
        <p className="font-display text-xl leading-relaxed text-content md:text-2xl">
          {scenario.logline}
        </p>
      )}

      {loreText && loreText !== scenario.logline && (
        <p className="mt-4 whitespace-pre-line font-sans text-[15px] leading-relaxed text-content-muted">
          {loreText}
        </p>
      )}

      {!scenario.logline && !loreText && (
        <p className="font-sans text-sm text-content-faint">
          No backstory recorded yet — start a playthrough to uncover it.
        </p>
      )}

      {scenario.narrator_persona && (
        <div className="mt-6 border-l-2 border-accent/60 pl-4">
          <p className="font-mono text-[11px] uppercase tracking-wider text-content-faint">
            Narrator tone
          </p>
          <p className="mt-1 font-sans text-sm italic text-content-muted">
            {scenario.narrator_persona}
          </p>
        </div>
      )}
    </section>
  );
};
