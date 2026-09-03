import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import { ExpressionBuilder } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder";
import { FieldExpression } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder.types";
import { InvariantFormProps } from "./InvariantForm.types";

interface InvariantFormState {
  label: string;
  narratorText: string;
  appliesTo: string;
  invariantExpression: FieldExpression | null;
}

const buildInitialState = (
  invariant: InvariantFormProps["invariant"],
  defaultAppliesTo: string,
): InvariantFormState => ({
  label: invariant?.label ?? "",
  narratorText: invariant?.narrator_text ?? "",
  appliesTo: invariant?.applies_to ?? defaultAppliesTo,
  invariantExpression:
    (invariant?.invariant_expression as FieldExpression | undefined) ?? null,
});

export const InvariantForm: React.FC<InvariantFormProps> = ({
  invariant,
  availableFields,
  appliesToOptions,
  onSubmit,
  onCancel,
  isSubmitting,
  submitError,
}) => {
  const [formState, setFormState] = useState<InvariantFormState>(() =>
    buildInitialState(invariant, appliesToOptions[0]?.value ?? "global"),
  );

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    onSubmit({
      label: formState.label,
      narrator_text: formState.narratorText,
      applies_to: formState.appliesTo,
      invariant_expression:
        (formState.invariantExpression as unknown as Record<
          string,
          unknown
        >) ?? {},
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
      <Select
        aria-label="Applies to"
        options={appliesToOptions}
        value={formState.appliesTo}
        onChange={(e) =>
          setFormState({ ...formState, appliesTo: e.target.value })
        }
      />
      <textarea
        value={formState.narratorText}
        onChange={(e) =>
          setFormState({ ...formState, narratorText: e.target.value })
        }
        placeholder="Narrator text"
        className="w-full border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300"
        rows={2}
        required
      />
      <ExpressionBuilder
        value={formState.invariantExpression}
        onChange={(expr) =>
          setFormState({ ...formState, invariantExpression: expr })
        }
        availableFields={availableFields}
      />
      {submitError && <p className="text-xs text-red-400">{submitError}</p>}
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
