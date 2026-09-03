import React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { EndConditionRowProps } from "./EndConditionsEditor.types";

const OUTCOME_BADGE_VARIANT = {
  win: "success",
  lose: "danger",
} as const;

const summarizeExpression = (expression: Record<string, unknown>): string => {
  const field = expression.field;
  const op = expression.op;
  const value = expression.value;
  if (typeof field !== "string" || typeof op !== "string") {
    return "No condition set";
  }
  return `${field} ${op} ${String(value)}`;
};

export const EndConditionRow: React.FC<EndConditionRowProps> = ({
  endCondition,
  onDelete,
}) => {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: endCondition.end_condition_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const handleDelete = (): void => onDelete(endCondition.end_condition_id);

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`end-condition-row-${endCondition.end_condition_id}`}
      className="flex items-center gap-3 border border-zinc-800 bg-zinc-950 px-3 py-2"
    >
      <button
        type="button"
        aria-label="Drag to reorder"
        className="cursor-grab text-zinc-600 hover:text-zinc-300"
        {...attributes}
        {...listeners}
      >
        ⠿
      </button>
      <Badge variant={OUTCOME_BADGE_VARIANT[endCondition.outcome_tag]}>
        {endCondition.outcome_tag}
      </Badge>
      {endCondition.is_secret && <Badge variant="warning">secret</Badge>}
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-medium text-zinc-100">
          {endCondition.outcome_title}
        </p>
        <p className="truncate text-xs text-zinc-500">
          {summarizeExpression(endCondition.condition_expression)}
        </p>
      </div>
      <Button variant="danger" size="sm" onClick={handleDelete}>
        Delete
      </Button>
    </div>
  );
};
