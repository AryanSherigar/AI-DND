import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { ExpressionBuilder } from "./ExpressionBuilder/ExpressionBuilder";
import { FieldExpression } from "./ExpressionBuilder/ExpressionBuilder.types";
import { StateMutation } from "../../types/condition.types";
import { StateMutationFields } from "./StateMutationFields";
import { ConditionFormProps } from "./ConditionForm.types";

interface ConditionFormState {
  label: string;
  narratorInstruction: string;
  conditionExpression: FieldExpression | null;
  stateMutation: StateMutation | null;
}

const buildInitialState = (
  condition: ConditionFormProps["condition"],
): ConditionFormState => ({
  label: condition?.label ?? "",
  narratorInstruction: condition?.narrator_instruction ?? "",
  conditionExpression:
    (condition?.condition_expression as FieldExpression | undefined) ?? null,
  stateMutation: condition?.state_mutation ?? null,
});

export const ConditionForm: React.FC<ConditionFormProps> = ({
  condition,
  availableFields,
  onSubmit,
  onCancel,
  isSubmitting,
  submitError,
}) => {
  const [formState, setFormState] = useState<ConditionFormState>(() =>
    buildInitialState(condition),
  );

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    onSubmit({
      label: formState.label,
      narrator_instruction: formState.narratorInstruction,
      condition_expression:
        (formState.conditionExpression as unknown as Record<string, unknown>) ??
        undefined,
      state_mutation: formState.stateMutation ?? undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Input
        value={formState.label}
        onChange={(e) => setFormState({ ...formState, label: e.target.value })}
        placeholder="Label"
        required
      />
      <textarea
        value={formState.narratorInstruction}
        onChange={(e) =>
          setFormState({ ...formState, narratorInstruction: e.target.value })
        }
        placeholder="Narrator instruction"
        className="rounded-md w-full border border-border-subtle bg-surface px-3 py-2 text-sm text-content-muted"
        rows={2}
        required
      />
      <ExpressionBuilder
        value={formState.conditionExpression}
        onChange={(expr) =>
          setFormState({ ...formState, conditionExpression: expr })
        }
        availableFields={availableFields}
      />
      <StateMutationFields
        value={formState.stateMutation}
        onChange={(mutation) =>
          setFormState({ ...formState, stateMutation: mutation })
        }
      />
      {submitError && <p className="text-xs text-danger">{submitError}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : "Save"}
        </Button>
      </div>
    </form>
  );
};
