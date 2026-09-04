import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import { OUTCOME_TAGS } from "../../types/end_condition.types";
import { ExpressionBuilder } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder";
import {
  EndConditionFormProps,
  EndConditionFormState,
} from "./EndConditionsEditor.types";

const OUTCOME_TAG_OPTIONS: SelectOption[] = OUTCOME_TAGS.map((tag) => ({
  value: tag,
  label: tag,
}));

const buildInitialState = (
  endCondition?: EndConditionFormProps["endCondition"],
): EndConditionFormState => ({
  outcomeTag: endCondition?.outcome_tag ?? "win",
  outcomeTitle: endCondition?.outcome_title ?? "",
  outcomeText: endCondition?.outcome_text ?? "",
  isSecret: endCondition?.is_secret ?? false,
  conditionExpression:
    (endCondition?.condition_expression as unknown as EndConditionFormState["conditionExpression"]) ??
    null,
});

export const EndConditionForm: React.FC<EndConditionFormProps> = ({
  availableFields,
  endCondition,
  onSubmit,
  onCancel,
  isSubmitting,
  submitError,
}) => {
  const [formState, setFormState] = useState<EndConditionFormState>(() =>
    buildInitialState(endCondition),
  );

  const canSubmit = Boolean(formState.outcomeTitle.trim());

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({
      outcome_tag: formState.outcomeTag,
      outcome_title: formState.outcomeTitle,
      outcome_text: formState.outcomeText,
      is_secret: formState.isSecret,
      condition_expression:
        (formState.conditionExpression as unknown as Record<string, unknown>) ??
        undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Select
        aria-label="Outcome tag"
        options={OUTCOME_TAG_OPTIONS}
        value={formState.outcomeTag}
        onChange={(e) =>
          setFormState({
            ...formState,
            outcomeTag: e.target.value as EndConditionFormState["outcomeTag"],
          })
        }
      />
      <Input
        aria-label="Outcome title"
        value={formState.outcomeTitle}
        onChange={(e) =>
          setFormState({ ...formState, outcomeTitle: e.target.value })
        }
        placeholder="Outcome title"
      />
      <textarea
        aria-label="Outcome text"
        value={formState.outcomeText}
        onChange={(e) =>
          setFormState({ ...formState, outcomeText: e.target.value })
        }
        placeholder="Outcome text"
        className="w-full rounded-none border border-zinc-800 bg-zinc-900 px-3 py-2 font-sans text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-400"
        rows={3}
      />
      <label className="flex items-center gap-2 text-sm text-zinc-300">
        <input
          type="checkbox"
          checked={formState.isSecret}
          onChange={(e) =>
            setFormState({ ...formState, isSecret: e.target.checked })
          }
        />
        Secret
      </label>
      <ExpressionBuilder
        value={formState.conditionExpression}
        onChange={(expr) =>
          setFormState({ ...formState, conditionExpression: expr })
        }
        availableFields={availableFields}
      />
      {submitError && <p className="text-xs text-red-400">{submitError}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={!canSubmit || isSubmitting}>
          {isSubmitting ? "Saving…" : "Save"}
        </Button>
      </div>
    </form>
  );
};
