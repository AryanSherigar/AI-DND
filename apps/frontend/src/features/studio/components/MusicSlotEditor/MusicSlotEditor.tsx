import React from "react";
import { ScenarioMood } from "@/shared/types/audio.types";
import { useScenarioMusic } from "../../hooks/useScenarioMusic";
import { MusicSlotEditorProps } from "./MusicSlotEditor.types";
import { MoodSlotCard } from "./MoodSlotCard";

const MOOD_LABELS: Record<ScenarioMood, string> = {
  peaceful: "Peaceful",
  mystery: "Mystery",
  tension: "Tension",
  combat: "Combat",
  melancholy: "Melancholy",
  triumph: "Triumph",
};

const MOOD_ORDER: ScenarioMood[] = [
  "peaceful",
  "mystery",
  "tension",
  "combat",
  "melancholy",
  "triumph",
];

export const MusicSlotEditor: React.FC<MusicSlotEditorProps> = ({
  scenarioId,
}) => {
  const { slots, isLoading, quota } = useScenarioMusic(scenarioId);
  const slotsByMood = new Map(slots.map((slot) => [slot.mood, slot]));
  const quotaExceeded = Boolean(
    quota &&
    (quota.scenario_generations_used >= quota.scenario_generations_limit ||
      quota.creator_generations_used_today >=
        quota.creator_generations_limit_per_day),
  );

  if (isLoading) {
    return <p className="text-sm text-content-muted">Loading mood tracks…</p>;
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-content">Mood Music</h2>
        <p className="text-sm text-content-faint">
          Set a track for each of the 6 moods your narrator can call for. All 6
          slots must be set (custom or default) before this scenario can be
          published.
        </p>
        {quota && (
          <p className="text-xs text-content-faint mt-1">
            Generations used: {quota.scenario_generations_used}/
            {quota.scenario_generations_limit} this scenario,{" "}
            {quota.creator_generations_used_today}/
            {quota.creator_generations_limit_per_day} today.
          </p>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {MOOD_ORDER.map((mood) => (
          <MoodSlotCard
            key={mood}
            scenarioId={scenarioId}
            mood={mood}
            label={MOOD_LABELS[mood]}
            slot={slotsByMood.get(mood)}
            quotaExceeded={quotaExceeded}
          />
        ))}
      </div>
    </div>
  );
};
