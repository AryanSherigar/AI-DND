import React from "react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { EntityRowProps } from "./EntityRow.types";

const ENTITY_TYPE_LABEL: Record<string, string> = {
  character: "Character",
  location: "Location",
  item: "Item",
  faction: "Faction",
  organization: "Organization",
};

export const EntityRow: React.FC<EntityRowProps> = ({
  entity,
  onEdit,
  onDelete,
}) => {
  const handleEditClick = (): void => onEdit(entity);
  const handleDeleteClick = (): void => onDelete(entity.entity_id);

  return (
    <div className="flex items-center justify-between border border-zinc-800 bg-zinc-900 px-3 py-2">
      <button
        type="button"
        onClick={handleEditClick}
        className="flex items-center gap-2 text-left"
      >
        <span className="text-sm text-zinc-200">{entity.canonical_name}</span>
        <Badge>{ENTITY_TYPE_LABEL[entity.entity_type]}</Badge>
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
