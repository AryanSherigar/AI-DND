import React from "react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { InvariantRowProps } from "./InvariantRow.types";

export const InvariantRow: React.FC<InvariantRowProps> = ({
  invariant,
  onEdit,
  onDelete,
}) => {
  const handleEditClick = (): void => onEdit(invariant);
  const handleDeleteClick = (): void => onDelete(invariant.invariant_id);

  return (
    <div className="flex items-center justify-between border border-zinc-800 bg-zinc-900 px-3 py-2">
      <button
        type="button"
        onClick={handleEditClick}
        className="flex flex-1 flex-col items-start gap-1 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-200">{invariant.label}</span>
          <Badge>{invariant.applies_to}</Badge>
        </div>
        <span className="text-xs text-zinc-500">{invariant.narrator_text}</span>
      </button>
      <Button
        type="button"
        variant="danger"
        size="sm"
        onClick={handleDeleteClick}
      >
        Delete
      </Button>
    </div>
  );
};
