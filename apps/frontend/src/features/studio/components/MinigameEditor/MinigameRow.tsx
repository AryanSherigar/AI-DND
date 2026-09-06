import React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { MinigameRowProps } from "./MinigameRow.types";

const TYPE_LABEL: Record<
  MinigameRowProps["minigame"]["minigame_type"],
  string
> = {
  dodge: "Dodge",
  replit_embed: "Replit Embed",
};

export const MinigameRow: React.FC<MinigameRowProps> = ({
  minigame,
  onEdit,
  onDelete,
}) => {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: minigame.minigame_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const handleEdit = (): void => onEdit(minigame);
  const handleDelete = (): void => onDelete(minigame.minigame_id);

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`minigame-row-${minigame.minigame_id}`}
      className="rounded-md flex items-center gap-3 border border-border-subtle bg-surface-inset px-3 py-2"
    >
      <button
        type="button"
        aria-label="Drag to reorder"
        className="cursor-grab text-content-faint hover:text-content-muted"
        {...attributes}
        {...listeners}
      >
        ⠿
      </button>
      <Badge>{TYPE_LABEL[minigame.minigame_type]}</Badge>
      <Badge variant="default">priority {minigame.priority}</Badge>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-content">
          {minigame.label}
        </p>
        <p className="truncate text-xs text-content-faint">
          {minigame.outcome_mode} outcome
        </p>
      </div>
      <Button variant="secondary" size="sm" onClick={handleEdit}>
        Edit
      </Button>
      <Button variant="danger" size="sm" onClick={handleDelete}>
        Delete
      </Button>
    </div>
  );
};
