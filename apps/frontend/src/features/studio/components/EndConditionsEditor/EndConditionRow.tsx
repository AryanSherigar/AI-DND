import React, { useState } from "react";
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
  onEdit,
  onDelete,
}) => {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: endCondition.end_condition_id });
  const [isExpanded, setIsExpanded] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const handleToggle = (): void => setIsExpanded((current) => !current);
  const handleEdit = (): void => onEdit(endCondition);
  const handleDelete = (): void => onDelete(endCondition.end_condition_id);

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`end-condition-row-${endCondition.end_condition_id}`}
      className="border border-zinc-800 bg-zinc-950 px-3 py-2"
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label="Drag to reorder"
          className="cursor-grab text-zinc-600 hover:text-zinc-300"
          {...attributes}
          {...listeners}
        >
          ⠿
        </button>
        <button
          type="button"
          onClick={handleToggle}
          aria-expanded={isExpanded}
          aria-label="Toggle details"
          className="text-zinc-500 hover:text-zinc-300"
        >
          <span
            className={`inline-block transition-transform ${isExpanded ? "rotate-90" : ""}`}
            aria-hidden="true"
          >
            ▸
          </span>
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
        <Button variant="secondary" size="sm" onClick={handleEdit}>
          Edit
        </Button>
        <Button variant="danger" size="sm" onClick={handleDelete}>
          Delete
        </Button>
      </div>
      {isExpanded && (
        <div className="mt-3 space-y-1 border-t border-zinc-800 pt-3 text-xs text-zinc-500">
          <p>{endCondition.outcome_text || "No outcome text set."}</p>
          <p className="text-zinc-600">
            Condition expression:{" "}
            {JSON.stringify(endCondition.condition_expression)}
          </p>
        </div>
      )}
    </div>
  );
};
