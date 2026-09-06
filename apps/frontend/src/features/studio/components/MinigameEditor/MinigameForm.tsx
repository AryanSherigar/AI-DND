import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import {
  MINIGAME_TYPE_OPTIONS,
  OUTCOME_MODE_OPTIONS,
} from "../../constants/minigame";
import {
  MinigameCreate,
  MinigameType,
  OutcomeMode,
  StateMutation,
  TieredOutcomeRange,
} from "../../types/minigame.types";
import { ExpressionBuilder } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder";
import { FieldExpression } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder.types";
import { StateMutationFields } from "../ConditionEditor/StateMutationFields";
import { DodgeDifficultySlider } from "./DodgeDifficultySlider";
import { MinigameFormProps } from "./MinigameForm.types";
import { ReplitTestConnectionButton } from "./ReplitTestConnectionButton";
import { TieredOutcomeRow } from "./TieredOutcomeRow";

const EMPTY_MUTATION: StateMutation = { path: "", op: "set", value: "" };
const DEFAULT_DODGE_DIFFICULTY = 3;

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
  replitEmbedUrl: minigame?.replit_embed_url ?? "",
});

const canSubmitForm = (formState: MinigameFormState): boolean => {
  if (!formState.label.trim()) return false;
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
      ? { difficulty: formState.dodgeDifficulty }
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
        <p className="mb-1 text-sm text-zinc-300">Trigger condition</p>
        <ExpressionBuilder
          value={formState.triggerConditionExpression}
          onChange={(expr) =>
            setFormState({ ...formState, triggerConditionExpression: expr })
          }
          availableFields={availableFields}
        />
      </div>

      <div>
        <p className="mb-1 text-sm text-zinc-300">Minigame type</p>
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
        <DodgeDifficultySlider
          value={formState.dodgeDifficulty}
          onChange={(dodgeDifficulty) =>
            setFormState({ ...formState, dodgeDifficulty })
          }
        />
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
        <p className="mb-1 text-sm text-zinc-300">Outcome mode</p>
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
            <p className="mb-1 text-sm text-zinc-300">On Win</p>
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
            <p className="mb-1 text-sm text-zinc-300">On Lose</p>
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
          <p className="text-sm text-zinc-300">Score ranges</p>
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
        </div>
      )}

      <div>
        <p className="mb-1 text-sm text-zinc-300">
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
          className="w-full rounded-none border border-zinc-800 bg-zinc-900 px-3 py-2 font-sans text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-400"
          rows={3}
        />
        <p className="mt-1 text-xs text-zinc-600">
          Use {"{outcome_tag}"} and {"{score}"} to substitute the resolved
          outcome into the narrator instruction.
        </p>
      </div>

      {submitError && <p className="text-xs text-red-400">{submitError}</p>}
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
