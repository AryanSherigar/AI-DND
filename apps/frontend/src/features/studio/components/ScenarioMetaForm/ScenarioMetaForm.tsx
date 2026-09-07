import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import {
  COMPLEXITY_TIER_LABELS,
  COMPLEXITY_TIERS,
} from "@/shared/constants/complexity-tiers";
import { ContentTag } from "@/shared/constants/content-tags";
import { useScenario } from "../../hooks/useScenario";
import { useServerSyncedState } from "../../hooks/useServerSyncedState";
import {
  ScenarioComplexityTier,
  ScenarioPlayerCountSupport,
} from "../../types/scenario.types";
import { ContentTagPicker } from "../PublishFlow/ContentTagPicker";
import { GenreTagsPicker } from "./GenreTagsPicker";
import { CoverImageUploader } from "../CoverImageUploader/CoverImageUploader";
import {
  ScenarioMetaFormProps,
  ScenarioMetaFormState,
} from "./ScenarioMetaForm.types";

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
  coverImageUrl: scenario.cover_image_url,
});

export const ScenarioMetaForm: React.FC<ScenarioMetaFormProps> = ({
  scenarioId,
}) => {
  const { scenario, isLoading, updateScenario, isUpdating, updateError } =
    useScenario(scenarioId);
  const [form, setForm] = useServerSyncedState<ScenarioMetaFormState>(
    scenario ? buildInitialState(scenario) : undefined,
  );

  const handleSave = (): void => {
    if (!form) return;
    updateScenario({
      title: form.title,
      logline: form.logline,
      genre_tags: form.genreTags,
      complexity_tier: form.complexityTier,
      content_tag: form.contentTag ?? undefined,
      player_count_support: form.playerCountSupport,
      cover_image_url: form.coverImageUrl ?? undefined,
    });
  };

  if (isLoading || !form) {
    return (
      <p className="text-sm text-content-faint">Loading scenario details...</p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-content">
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
      {updateError && <p className="text-xs text-danger">{updateError}</p>}
      <div className="space-y-1">
        <label className="text-xs text-content-faint">Title</label>
        <Input
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-content-faint">Logline</label>
        <Input
          value={form.logline}
          onChange={(e) => setForm({ ...form, logline: e.target.value })}
        />
      </div>
      <CoverImageUploader
        label="Cover Image"
        value={form.coverImageUrl}
        onChange={(url) => setForm({ ...form, coverImageUrl: url })}
      />
      <div className="space-y-1">
        <label className="text-xs text-content-faint">Genre Tags</label>
        <GenreTagsPicker
          selected={form.genreTags}
          onChange={(genreTags) => setForm({ ...form, genreTags })}
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-content-faint">Complexity Tier</label>
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
        <label className="text-xs text-content-faint">
          Player Count Support
        </label>
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
