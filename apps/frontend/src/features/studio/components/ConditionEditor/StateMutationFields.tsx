import React from "react";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import { StateMutationOp } from "../../types/condition.types";
import { StateMutationFieldsProps } from "./StateMutationFields.types";

const MUTATION_OP_OPTIONS: { value: StateMutationOp; label: string }[] = [
  { value: "set", label: "set" },
  { value: "increment", label: "increment" },
  { value: "decrement", label: "decrement" },
];

const EMPTY_MUTATION = { path: "", op: "set" as StateMutationOp, value: "" };

export const StateMutationFields: React.FC<StateMutationFieldsProps> = ({
  value,
  onChange,
}) => {
  const hasStateMutation = value !== null;

  const handleToggle = (event: React.ChangeEvent<HTMLInputElement>): void => {
    onChange(event.target.checked ? EMPTY_MUTATION : null);
  };

  const handlePathChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    if (!value) return;
    onChange({ ...value, path: event.target.value });
  };

  const handleOpChange = (event: React.ChangeEvent<HTMLSelectElement>): void => {
    if (!value) return;
    onChange({ ...value, op: event.target.value as StateMutationOp });
  };

  const handleValueChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    if (!value) return;
    onChange({ ...value, value: event.target.value });
  };

  return (
    <div className="space-y-2 border border-zinc-800 p-3">
      <label className="flex items-center gap-2 text-sm text-zinc-300">
        <input
          type="checkbox"
          checked={hasStateMutation}
          onChange={handleToggle}
        />
        Has state mutation (Effect C)
      </label>
      {hasStateMutation && (
        <div className="flex items-center gap-2">
          <Input
            value={value.path}
            onChange={handlePathChange}
            placeholder="path, e.g. player.sanity"
            aria-label="Mutation path"
          />
          <div className="w-36 flex-shrink-0">
            <Select
              aria-label="Mutation operation"
              options={MUTATION_OP_OPTIONS}
              value={value.op}
              onChange={handleOpChange}
            />
          </div>
          <Input
            value={String(value.value)}
            onChange={handleValueChange}
            placeholder="value"
            aria-label="Mutation value"
          />
        </div>
      )}
    </div>
  );
};
