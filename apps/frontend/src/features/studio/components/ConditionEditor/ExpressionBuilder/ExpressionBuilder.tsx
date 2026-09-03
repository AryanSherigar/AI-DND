import React from "react";
import { Button } from "../../../../../shared/components/ui/Button";
import { FieldPicker } from "./FieldPicker";
import { OperatorPicker } from "./OperatorPicker";
import { ValueInput } from "./ValueInput";
import {
  ExpressionBuilderProps,
  ExpressionOperator,
  FieldExpression,
} from "./ExpressionBuilder.types";

const DEFAULT_OPERATOR: ExpressionOperator = "==";

type ClauseKind = "AND" | "OR" | "NOT";
const CLAUSE_KINDS: ClauseKind[] = ["AND", "OR", "NOT"];

const buildEmptyClause = (): FieldExpression => ({
  field: "",
  op: DEFAULT_OPERATOR,
  value: "",
});

const withUpdates = (
  current: FieldExpression | null,
  updates: Partial<FieldExpression>,
): FieldExpression => ({
  field: current?.field ?? "",
  op: current?.op ?? DEFAULT_OPERATOR,
  value: current?.value ?? "",
  ...(current?.AND ? { AND: current.AND } : {}),
  ...(current?.OR ? { OR: current.OR } : {}),
  ...(current?.NOT ? { NOT: current.NOT } : {}),
  ...updates,
});

export const ExpressionBuilder: React.FC<ExpressionBuilderProps> = ({
  value,
  onChange,
  availableFields,
}) => {
  const field = value?.field ?? "";
  const op = value?.op ?? DEFAULT_OPERATOR;
  const fieldValue = value?.value ?? "";
  const selectedField = availableFields.find((item) => item.path === field);

  const handleFieldChange = (path: string): void =>
    onChange(withUpdates(value, { field: path }));

  const handleOpChange = (nextOp: ExpressionOperator): void =>
    onChange(withUpdates(value, { op: nextOp }));

  const handleValueChange = (nextValue: string | number | boolean): void =>
    onChange(withUpdates(value, { value: nextValue }));

  const handleAddClause = (kind: ClauseKind): void =>
    onChange(withUpdates(value, { [kind]: buildEmptyClause() }));

  const handleRemoveClause = (kind: ClauseKind): void => {
    const next = withUpdates(value, {});
    delete next[kind];
    onChange(next);
  };

  const handleClauseChange = (
    kind: ClauseKind,
    clause: FieldExpression | null,
  ): void => {
    if (clause === null) {
      handleRemoveClause(kind);
      return;
    }
    onChange(withUpdates(value, { [kind]: clause }));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <FieldPicker
            value={field}
            onChange={handleFieldChange}
            availableFields={availableFields}
          />
        </div>
        <div className="w-40 flex-shrink-0">
          <OperatorPicker value={op} onChange={handleOpChange} />
        </div>
        <div className="flex-1">
          <ValueInput
            value={fieldValue}
            onChange={handleValueChange}
            fieldType={selectedField?.type}
          />
        </div>
      </div>

      <div className="flex gap-2">
        {CLAUSE_KINDS.filter((kind) => !value?.[kind]).map((kind) => (
          <Button
            key={kind}
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => handleAddClause(kind)}
          >
            + {kind}
          </Button>
        ))}
      </div>

      {CLAUSE_KINDS.filter((kind) => value?.[kind]).map((kind) => (
        <div key={kind} className="ml-4 border-l border-zinc-800 pl-4">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-medium uppercase text-zinc-500">
              {kind}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => handleRemoveClause(kind)}
            >
              Remove
            </Button>
          </div>
          <ExpressionBuilder
            value={value?.[kind] ?? null}
            onChange={(clause) => handleClauseChange(kind, clause)}
            availableFields={availableFields}
          />
        </div>
      ))}
    </div>
  );
};
