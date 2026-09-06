import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { StateMutationFields } from "../ConditionEditor/StateMutationFields";
import { TieredOutcomeRowProps } from "./TieredOutcomeRow.types";

export const TieredOutcomeRow: React.FC<TieredOutcomeRowProps> = ({
  value,
  onChange,
  onRemove,
}) => {
  const handleMinScoreChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => onChange({ ...value, min_score: Number(event.target.value) });

  const handleMaxScoreChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ): void => onChange({ ...value, max_score: Number(event.target.value) });

  const handleMutationChange: React.ComponentProps<
    typeof StateMutationFields
  >["onChange"] = (mutation) => {
    if (!mutation) return;
    onChange({ ...value, mutation });
  };

  return (
    <div className="space-y-2 border border-zinc-800 bg-zinc-900 p-3">
      <div className="flex items-center gap-2">
        <Input
          type="number"
          aria-label="Minimum score"
          value={value.min_score}
          onChange={handleMinScoreChange}
          placeholder="Min score"
        />
        <span className="text-zinc-600">–</span>
        <Input
          type="number"
          aria-label="Maximum score"
          value={value.max_score}
          onChange={handleMaxScoreChange}
          placeholder="Max score"
        />
        <Button type="button" variant="danger" size="sm" onClick={onRemove}>
          Remove
        </Button>
      </div>
      <StateMutationFields
        value={value.mutation}
        onChange={handleMutationChange}
        isOptional={false}
      />
    </div>
  );
};
