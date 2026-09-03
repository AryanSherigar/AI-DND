import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import {
  COMPLEXITY_TIER_LABELS,
  COMPLEXITY_TIERS,
} from "@/shared/constants/complexity-tiers";
import { ContentTag } from "@/shared/constants/content-tags";
import { useScenario } from "../../hooks/useScenario";
import {
  ScenarioComplexityTier,
  ScenarioPlayerCountSupport,
} from "../../types/scenario.types";
import { ContentTagPicker } from "../PublishFlow/ContentTagPicker";
import { GenreTagsPicker } from "./GenreTagsPicker";
import { ScenarioMetaFormProps, ScenarioMetaFormState } from "./ScenarioMetaForm.types";

const PLAYER_COUNT_SUPPORT_OPTIONS: SelectOption[] = [
  { value: "solo", label: "Solo" },
  { value: "multiplayer", label: "Multiplayer" },
  { value: "both", label: "Both" },
];

const COMPLEXITY_TIER_OPTIONS: SelectOption[] = COMPLEXITY_TIERS.map(
  (tier) => ({ value: tier, label: COMPLEXITY_TIER_LABELS[tier] }),
);

const buildInitialState = (
  scenario: NonNullable<ReturnType<typeof useScenario>["scenario"]>,
): ScenarioMetaFormState => ({
  title: scenario.title,
  logline: scenario.logline ?? "",
  genreTags: scenario.genre_tags,
  complexityTier: scenario.complexity_tier,
  contentTag: scenario.content_tag,
  playerCountSupport: scenario.player_count_support,
});

export const ScenarioMetaForm: React.FC<ScenarioMetaFormProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [form, setForm] = useState<ScenarioMetaFormState | null>(null);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (scenario && !hasInitialized.current) {
      setForm(buildInitialState(scenario));
      hasInitialized.current = true;
    }
  }, [scenario]);

  const handleSave = (): void => {
    if (!form) return;
    updateScenario({
      title: form.title,
      logline: form.logline,
      genre_tags: form.genreTags,
      complexity_tier: form.complexityTier,
      content_tag: form.contentTag ?? undefined,
      player_count_support: form.playerCountSupport,
    });
  };

  if (isLoading || !form) {
    return <p className="text-sm text-zinc-500">Loading scenario details...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">
          Scenario Details
        </h2>
        <Button
          type="button"
          variant="primary"
          size="sm"
          onClick={handleSave}
          disabled={isUpdating}
        >
          {isUpdating ? "Saving..." : "Save"}
        </Button>
      </div>
      {updateError && <p className="text-xs text-red-400">{updateError}</p>}
      <div className="space-y-1">
        <label className="text-xs text-zinc-500">Title</label>
        <Input
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-zinc-500">Logline</label>
        <Input
          value={form.logline}
          onChange={(e) => setForm({ ...form, logline: e.target.value })}
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-zinc-500">Genre Tags</label>
        <GenreTagsPicker
          selected={form.genreTags}
          onChange={(genreTags) => setForm({ ...form, genreTags })}
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-zinc-500">Complexity Tier</label>
        <Select
          options={COMPLEXITY_TIER_OPTIONS}
          value={form.complexityTier}
          onChange={(e) =>
            setForm({
              ...form,
              complexityTier: e.target.value as ScenarioComplexityTier,
            })
          }
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-zinc-500">Player Count Support</label>
        <Select
          options={PLAYER_COUNT_SUPPORT_OPTIONS}
          value={form.playerCountSupport}
          onChange={(e) =>
            setForm({
              ...form,
              playerCountSupport: e.target.value as ScenarioPlayerCountSupport,
            })
          }
        />
      </div>
      <ContentTagPicker
        value={form.contentTag}
        onChange={(tag: ContentTag) => setForm({ ...form, contentTag: tag })}
      />
    </div>
  );
};
