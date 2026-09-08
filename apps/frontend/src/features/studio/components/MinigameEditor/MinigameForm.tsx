import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import {
  MINIGAME_TYPE_OPTIONS,
  OUTCOME_MODE_OPTIONS,
} from "../../constants/minigame";
import {
  DEFAULT_DODGE_CONFIG,
  DodgeConfigShape,
  MinigameCreate,
  MinigameType,
  OutcomeMode,
  StateMutation,
  TieredOutcomeRange,
} from "../../types/minigame.types";
import { CoverImageUploader } from "../CoverImageUploader/CoverImageUploader";
import { useUploadScenarioAudio } from "../../hooks/useUploadScenarioAudio";
import {
  ALLOWED_SCENARIO_AUDIO_ACCEPT,
  ALLOWED_SCENARIO_AUDIO_TYPES,
  MAX_SCENARIO_AUDIO_BYTES,
} from "../../constants/upload";
import { ExpressionBuilder } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder";
import { FieldExpression } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder.types";
import { StateMutationFields } from "../ConditionEditor/StateMutationFields";
import { DodgeDifficultySlider } from "./DodgeDifficultySlider";
import { MinigameFormProps } from "./MinigameForm.types";
import { ReplitTestConnectionButton } from "./ReplitTestConnectionButton";
import { TieredOutcomeRow } from "./TieredOutcomeRow";

const EMPTY_MUTATION: StateMutation = { path: "", op: "set", value: "" };
const DEFAULT_DODGE_DIFFICULTY = 3;

const tierRangesOverlap = (ranges: TieredOutcomeRange[]): boolean => {
  const ordered = [...ranges].sort(
    (left, right) => left.min_score - right.min_score,
  );
  return ordered.some(
    (range, index) =>
      index > 0 && range.min_score <= ordered[index - 1].max_score,
  );
};

interface MinigameFormState {
  label: string;
  minigameType: MinigameType;
  triggerConditionExpression: FieldExpression | null;
  outcomeMode: OutcomeMode;
  winMutation: StateMutation;
  loseMutation: StateMutation;
  tieredOutcomes: TieredOutcomeRange[];
  timeoutMutation: StateMutation;
  narratorInstructionTemplate: string;
  dodgeDifficulty: number;
  dodgeConfig: DodgeConfigShape;
  replitEmbedUrl: string;
}

const buildInitialState = (
  minigame: MinigameFormProps["minigame"],
): MinigameFormState => ({
  label: minigame?.label ?? "",
  minigameType: minigame?.minigame_type ?? "dodge",
  triggerConditionExpression:
    (minigame?.trigger_condition_expression as unknown as FieldExpression) ??
    null,
  outcomeMode: minigame?.outcome_mode ?? "binary",
  winMutation: minigame?.win_mutation ?? EMPTY_MUTATION,
  loseMutation: minigame?.lose_mutation ?? EMPTY_MUTATION,
  tieredOutcomes: minigame?.tiered_outcomes ?? [],
  timeoutMutation: minigame?.timeout_mutation ?? EMPTY_MUTATION,
  narratorInstructionTemplate: minigame?.narrator_instruction_template ?? "",
  dodgeDifficulty:
    minigame?.dodge_config?.difficulty ?? DEFAULT_DODGE_DIFFICULTY,
  dodgeConfig: {
    ...DEFAULT_DODGE_CONFIG,
    ...minigame?.dodge_config,
    audio: { ...DEFAULT_DODGE_CONFIG.audio!, ...minigame?.dodge_config?.audio },
    copy: { ...DEFAULT_DODGE_CONFIG.copy!, ...minigame?.dodge_config?.copy },
    performance_thresholds: {
      ...DEFAULT_DODGE_CONFIG.performance_thresholds!,
      ...minigame?.dodge_config?.performance_thresholds,
    },
  },
  replitEmbedUrl: minigame?.replit_embed_url ?? "",
});

const canSubmitForm = (formState: MinigameFormState): boolean => {
  if (!formState.label.trim()) return false;
  if (
    formState.minigameType === "dodge" &&
    !formState.dodgeConfig.enabled_patterns?.length
  ) {
    return false;
  }
  if (
    formState.minigameType === "dodge" &&
    (formState.dodgeConfig.performance_thresholds?.survive_min_health ?? 1) >
      (formState.dodgeConfig.performance_thresholds?.excellent_min_health ?? 3)
  ) {
    return false;
  }
  if (
    formState.minigameType === "replit_embed" &&
    !formState.replitEmbedUrl.trim()
  ) {
    return false;
  }
  if (
    formState.outcomeMode === "tiered" &&
    formState.tieredOutcomes.length === 0
  ) {
    return false;
  }
  if (
    formState.outcomeMode === "tiered" &&
    formState.tieredOutcomes.some((range) => range.min_score > range.max_score)
  ) {
    return false;
  }
  if (
    formState.outcomeMode === "tiered" &&
    tierRangesOverlap(formState.tieredOutcomes)
  ) {
    return false;
  }
  return true;
};

const buildPayload = (formState: MinigameFormState): MinigameCreate => ({
  label: formState.label,
  minigame_type: formState.minigameType,
  trigger_condition_expression:
    (formState.triggerConditionExpression as unknown as Record<
      string,
      unknown
    >) ?? undefined,
  outcome_mode: formState.outcomeMode,
  win_mutation:
    formState.outcomeMode === "binary" ? formState.winMutation : null,
  lose_mutation:
    formState.outcomeMode === "binary" ? formState.loseMutation : null,
  tiered_outcomes:
    formState.outcomeMode === "tiered" ? formState.tieredOutcomes : [],
  timeout_mutation: formState.timeoutMutation,
  narrator_instruction_template: formState.narratorInstructionTemplate || null,
  dodge_config:
    formState.minigameType === "dodge"
      ? { ...formState.dodgeConfig, difficulty: formState.dodgeDifficulty }
      : null,
  replit_embed_url:
    formState.minigameType === "replit_embed" ? formState.replitEmbedUrl : null,
});

export const MinigameForm: React.FC<MinigameFormProps> = ({
  availableFields,
  minigame,
  onSubmit,
  onCancel,
  isSubmitting,
  submitError,
}) => {
  const [formState, setFormState] = useState<MinigameFormState>(() =>
    buildInitialState(minigame),
  );
  const [audioUploadError, setAudioUploadError] = useState<string | null>(null);
  const uploadScenarioAudio = useUploadScenarioAudio();

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    if (!canSubmitForm(formState)) return;
    onSubmit(buildPayload(formState));
  };

  const handleAddTieredOutcome = (): void => {
    setFormState({
      ...formState,
      tieredOutcomes: [
        ...formState.tieredOutcomes,
        { min_score: 0, max_score: 0, mutation: EMPTY_MUTATION },
      ],
    });
  };

  const handleTieredOutcomeChange =
    (index: number) =>
    (range: TieredOutcomeRange): void => {
      const tieredOutcomes = [...formState.tieredOutcomes];
      tieredOutcomes[index] = range;
      setFormState({ ...formState, tieredOutcomes });
    };

  const handleRemoveTieredOutcome = (index: number) => (): void => {
    setFormState({
      ...formState,
      tieredOutcomes: formState.tieredOutcomes.filter((_, i) => i !== index),
    });
  };

  const updateDodgeConfig = (patch: Partial<DodgeConfigShape>): void =>
    setFormState({
      ...formState,
      dodgeConfig: { ...formState.dodgeConfig, ...patch },
    });

  const togglePattern = (
    pattern: NonNullable<DodgeConfigShape["enabled_patterns"]>[number],
  ): void => {
    const enabled = formState.dodgeConfig.enabled_patterns ?? [];
    // The API requires one curated pattern. Do not let a creator accidentally
    // create an unwinnable/no-op encounter by clearing the final choice.
    if (enabled.length === 1 && enabled.includes(pattern)) return;
    const next = enabled.includes(pattern)
      ? enabled.filter((item) => item !== pattern)
      : [...enabled, pattern];
    updateDodgeConfig({ enabled_patterns: next, pattern_order: next });
  };

  const handleAudioUpload = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setAudioUploadError(null);
    if (!ALLOWED_SCENARIO_AUDIO_TYPES.includes(file.type)) {
      setAudioUploadError("Use MP3, OGG, or WAV audio.");
      return;
    }
    if (file.size > MAX_SCENARIO_AUDIO_BYTES) {
      setAudioUploadError("Audio exceeds the 10MB size limit.");
      return;
    }
    uploadScenarioAudio.mutate(file, {
      onSuccess: (data) =>
        updateDodgeConfig({
          audio: {
            ...(formState.dodgeConfig.audio ?? DEFAULT_DODGE_CONFIG.audio!),
            music_asset_url: data.url,
          },
        }),
      onError: () =>
        setAudioUploadError("Audio upload failed — please try again."),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        aria-label="Label"
        value={formState.label}
        onChange={(e) => setFormState({ ...formState, label: e.target.value })}
        placeholder="Label"
        required
      />

      <div>
        <p className="mb-1 text-sm text-content-muted">Trigger condition</p>
        <ExpressionBuilder
          value={formState.triggerConditionExpression}
          onChange={(expr) =>
            setFormState({ ...formState, triggerConditionExpression: expr })
          }
          availableFields={availableFields}
        />
      </div>

      <div>
        <p className="mb-1 text-sm text-content-muted">Minigame type</p>
        <Select
          aria-label="Minigame type"
          options={[...MINIGAME_TYPE_OPTIONS]}
          value={formState.minigameType}
          onChange={(e) =>
            setFormState({
              ...formState,
              minigameType: e.target.value as MinigameType,
            })
          }
        />
      </div>

      {formState.minigameType === "dodge" && (
        <>
          <DodgeDifficultySlider
            value={formState.dodgeDifficulty}
            onChange={(dodgeDifficulty) =>
              setFormState({ ...formState, dodgeDifficulty })
            }
          />
          <details className="rounded-md border border-border-subtle bg-surface-inset p-3">
            <summary className="cursor-pointer text-sm font-medium text-content">
              Safe dodge overrides & presentation
            </summary>
            <div className="mt-3 space-y-4">
              <p className="text-xs text-content-faint">
                Hitboxes are fixed for fairness. Longer encounters with low
                health or short invulnerability can be difficult even at a low
                preset.
              </p>
              {(formState.dodgeConfig.duration_seconds ?? 15) > 60 &&
                (formState.dodgeConfig.health ?? 3) < 3 && (
                  <p className="text-xs text-warning">
                    Fairness warning: a long encounter with fewer than 3 health
                    is likely unforgiving.
                  </p>
                )}
              <div className="grid grid-cols-3 gap-2">
                <Input
                  aria-label="Duration seconds"
                  type="number"
                  min={10}
                  max={120}
                  value={formState.dodgeConfig.duration_seconds ?? 15}
                  onChange={(e) =>
                    updateDodgeConfig({
                      duration_seconds: Number(e.target.value),
                    })
                  }
                />
                <Input
                  aria-label="Health"
                  type="number"
                  min={1}
                  max={10}
                  value={formState.dodgeConfig.health ?? 3}
                  onChange={(e) =>
                    updateDodgeConfig({ health: Number(e.target.value) })
                  }
                />
                <Input
                  aria-label="Invulnerability milliseconds"
                  type="number"
                  min={250}
                  max={3000}
                  value={formState.dodgeConfig.invulnerability_ms ?? 1000}
                  onChange={(e) =>
                    updateDodgeConfig({
                      invulnerability_ms: Number(e.target.value),
                    })
                  }
                />
              </div>
              <div>
                <p className="mb-1 text-sm text-content-muted">
                  Enabled patterns (run in this order)
                </p>
                <div className="flex gap-3">
                  {(["rain", "ring", "beam", "homing"] as const).map(
                    (pattern) => (
                      <label
                        key={pattern}
                        className="text-sm text-content-muted"
                      >
                        <input
                          type="checkbox"
                          checked={
                            formState.dodgeConfig.enabled_patterns?.includes(
                              pattern,
                            ) ?? false
                          }
                          disabled={
                            (formState.dodgeConfig.enabled_patterns?.length ??
                              0) === 1 &&
                            formState.dodgeConfig.enabled_patterns?.includes(
                              pattern,
                            )
                          }
                          onChange={() => togglePattern(pattern)}
                        />{" "}
                        {pattern}
                      </label>
                    ),
                  )}
                </div>
                <p className="mt-1 text-xs text-content-faint">
                  Uncheck patterns to disable them; checked patterns retain this
                  curated order. At least one pattern is required.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  aria-label="Excellent minimum health"
                  type="number"
                  min={0}
                  max={10}
                  value={
                    formState.dodgeConfig.performance_thresholds
                      ?.excellent_min_health ?? 3
                  }
                  onChange={(e) =>
                    updateDodgeConfig({
                      performance_thresholds: {
                        ...(formState.dodgeConfig.performance_thresholds ??
                          DEFAULT_DODGE_CONFIG.performance_thresholds!),
                        excellent_min_health: Number(e.target.value),
                      },
                    })
                  }
                />
                <Input
                  aria-label="Survive minimum health"
                  type="number"
                  min={0}
                  max={10}
                  value={
                    formState.dodgeConfig.performance_thresholds
                      ?.survive_min_health ?? 1
                  }
                  onChange={(e) =>
                    updateDodgeConfig({
                      performance_thresholds: {
                        ...(formState.dodgeConfig.performance_thresholds ??
                          DEFAULT_DODGE_CONFIG.performance_thresholds!),
                        survive_min_health: Number(e.target.value),
                      },
                    })
                  }
                />
              </div>
              {(formState.dodgeConfig.performance_thresholds
                ?.survive_min_health ?? 1) >
                (formState.dodgeConfig.performance_thresholds
                  ?.excellent_min_health ?? 3) && (
                <p className="text-xs text-danger">
                  Survive minimum health cannot exceed excellent minimum health.
                </p>
              )}
              <div className="grid grid-cols-3 gap-2">
                <Select
                  aria-label="Player style"
                  value={formState.dodgeConfig.player_style ?? "soul"}
                  options={[
                    { value: "soul", label: "Soul" },
                    { value: "heart", label: "Heart" },
                    { value: "spark", label: "Spark" },
                  ]}
                  onChange={(e) =>
                    updateDodgeConfig({
                      player_style: e.target
                        .value as DodgeConfigShape["player_style"],
                    })
                  }
                />
                <Select
                  aria-label="Obstacle style"
                  value={formState.dodgeConfig.obstacle_style ?? "ash"}
                  options={[
                    { value: "ash", label: "Ash" },
                    { value: "neon", label: "Neon" },
                    { value: "crystal", label: "Crystal" },
                  ]}
                  onChange={(e) =>
                    updateDodgeConfig({
                      obstacle_style: e.target
                        .value as DodgeConfigShape["obstacle_style"],
                    })
                  }
                />
                <Input
                  aria-label="Obstacle color"
                  type="color"
                  value={formState.dodgeConfig.obstacle_color ?? "#ff8a65"}
                  onChange={(e) =>
                    updateDodgeConfig({ obstacle_color: e.target.value })
                  }
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <Select
                  aria-label="Arena background"
                  value={formState.dodgeConfig.background ?? "void"}
                  options={[
                    { value: "void", label: "Void" },
                    { value: "ember", label: "Ember" },
                    { value: "midnight", label: "Midnight" },
                  ]}
                  onChange={(e) =>
                    updateDodgeConfig({
                      background: e.target
                        .value as DodgeConfigShape["background"],
                    })
                  }
                />
                <Select
                  aria-label="Arena texture"
                  value={formState.dodgeConfig.texture ?? "none"}
                  options={[
                    { value: "none", label: "None" },
                    { value: "grain", label: "Grain" },
                    { value: "stars", label: "Stars" },
                  ]}
                  onChange={(e) =>
                    updateDodgeConfig({
                      texture: e.target.value as DodgeConfigShape["texture"],
                    })
                  }
                />
                <Select
                  aria-label="Palette"
                  value={formState.dodgeConfig.palette ?? "ashfall"}
                  options={[
                    { value: "ashfall", label: "Ashfall" },
                    { value: "ember", label: "Ember" },
                    { value: "aurora", label: "Aurora" },
                  ]}
                  onChange={(e) =>
                    updateDodgeConfig({
                      palette: e.target.value as DodgeConfigShape["palette"],
                    })
                  }
                />
              </div>
              <CoverImageUploader
                value={formState.dodgeConfig.background_asset_url ?? null}
                onChange={(background_asset_url) =>
                  updateDodgeConfig({ background_asset_url })
                }
                label="Custom arena background"
                description="Optional uploaded image only; no external URLs."
              />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label
                    htmlFor="dodge-audio-upload"
                    className="block text-xs text-content-muted"
                  >
                    Encounter audio (MP3, OGG, WAV; 10MB max)
                  </label>
                  <input
                    id="dodge-audio-upload"
                    aria-label="Upload encounter audio"
                    type="file"
                    accept={ALLOWED_SCENARIO_AUDIO_ACCEPT}
                    onChange={handleAudioUpload}
                    disabled={uploadScenarioAudio.isPending}
                    className="mt-1 text-xs text-content-muted"
                  />
                  {formState.dodgeConfig.audio?.music_asset_url && (
                    <p className="mt-1 text-xs text-content-faint">
                      Audio uploaded
                    </p>
                  )}
                  {audioUploadError && (
                    <p className="mt-1 text-xs text-danger">
                      {audioUploadError}
                    </p>
                  )}
                </div>
                <Input
                  aria-label="Audio volume"
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={formState.dodgeConfig.audio?.volume ?? 0.7}
                  onChange={(e) =>
                    updateDodgeConfig({
                      audio: {
                        ...(formState.dodgeConfig.audio ??
                          DEFAULT_DODGE_CONFIG.audio!),
                        volume: Number(e.target.value),
                      },
                    })
                  }
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {(
                  [
                    "instructions",
                    "start_text",
                    "win_text",
                    "lose_text",
                  ] as const
                ).map((field) => (
                  <Input
                    key={field}
                    aria-label={`Dodge ${field.replace("_", " ")}`}
                    value={formState.dodgeConfig.copy?.[field] ?? ""}
                    onChange={(e) =>
                      updateDodgeConfig({
                        copy: {
                          ...(formState.dodgeConfig.copy ??
                            DEFAULT_DODGE_CONFIG.copy!),
                          [field]: e.target.value,
                        },
                      })
                    }
                  />
                ))}
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() =>
                  setFormState({
                    ...formState,
                    dodgeDifficulty: DEFAULT_DODGE_DIFFICULTY,
                    dodgeConfig: { ...DEFAULT_DODGE_CONFIG },
                  })
                }
              >
                Reset dodge defaults
              </Button>
            </div>
          </details>
        </>
      )}

      {formState.minigameType === "replit_embed" && (
        <div className="space-y-2">
          <Input
            aria-label="Replit embed URL"
            value={formState.replitEmbedUrl}
            onChange={(e) =>
              setFormState({ ...formState, replitEmbedUrl: e.target.value })
            }
            placeholder="https://your-repl.replit.app"
          />
          <ReplitTestConnectionButton embedUrl={formState.replitEmbedUrl} />
        </div>
      )}

      <div>
        <p className="mb-1 text-sm text-content-muted">Outcome mode</p>
        <Select
          aria-label="Outcome mode"
          options={[...OUTCOME_MODE_OPTIONS]}
          value={formState.outcomeMode}
          onChange={(e) =>
            setFormState({
              ...formState,
              outcomeMode: e.target.value as OutcomeMode,
            })
          }
        />
      </div>

      {formState.outcomeMode === "binary" && (
        <div className="space-y-3">
          <div>
            <p className="mb-1 text-sm text-content-muted">On Win</p>
            <StateMutationFields
              value={formState.winMutation}
              onChange={(mutation) =>
                setFormState({
                  ...formState,
                  winMutation: mutation ?? EMPTY_MUTATION,
                })
              }
              isOptional={false}
            />
          </div>
          <div>
            <p className="mb-1 text-sm text-content-muted">On Lose</p>
            <StateMutationFields
              value={formState.loseMutation}
              onChange={(mutation) =>
                setFormState({
                  ...formState,
                  loseMutation: mutation ?? EMPTY_MUTATION,
                })
              }
              isOptional={false}
            />
          </div>
        </div>
      )}

      {formState.outcomeMode === "tiered" && (
        <div className="space-y-2">
          <p className="text-sm text-content-muted">Score ranges</p>
          {formState.tieredOutcomes.map((range, index) => (
            <TieredOutcomeRow
              key={index}
              value={range}
              onChange={handleTieredOutcomeChange(index)}
              onRemove={handleRemoveTieredOutcome(index)}
            />
          ))}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleAddTieredOutcome}
          >
            + Add score range
          </Button>
          {formState.tieredOutcomes.some(
            (range) => range.min_score > range.max_score,
          ) && (
            <p className="text-xs text-danger">
              Each score range must have a minimum no greater than its maximum.
            </p>
          )}
          {tierRangesOverlap(formState.tieredOutcomes) && (
            <p className="text-xs text-danger">
              Score ranges cannot overlap; boundary scores belong to one tier
              only.
            </p>
          )}
        </div>
      )}

      <div>
        <p className="mb-1 text-sm text-content-muted">
          On Connection Failure / Timeout
        </p>
        <StateMutationFields
          value={formState.timeoutMutation}
          onChange={(mutation) =>
            setFormState({
              ...formState,
              timeoutMutation: mutation ?? EMPTY_MUTATION,
            })
          }
          isOptional={false}
        />
      </div>

      <div>
        <textarea
          aria-label="Narrator instruction template"
          value={formState.narratorInstructionTemplate}
          onChange={(e) =>
            setFormState({
              ...formState,
              narratorInstructionTemplate: e.target.value,
            })
          }
          placeholder="Narrator instruction template"
          className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2 font-sans text-sm text-content-muted placeholder:text-content-faint focus:outline-none focus-visible:border-accent/50"
          rows={3}
        />
        <p className="mt-1 text-xs text-content-faint">
          Use {"{outcome_tag}"} and {"{score}"} to substitute the resolved
          outcome into the narrator instruction.
        </p>
      </div>

      {submitError && <p className="text-xs text-danger">{submitError}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={!canSubmitForm(formState) || isSubmitting}
        >
          {isSubmitting ? "Saving…" : "Save"}
        </Button>
      </div>
    </form>
  );
};
