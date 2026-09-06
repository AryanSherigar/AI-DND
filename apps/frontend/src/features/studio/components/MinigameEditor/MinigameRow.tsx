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
      <Badge>{TYPE_LABEL[minigame.minigame_type]}</Badge>
      <Badge variant="default">priority {minigame.priority}</Badge>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-zinc-100">
          {minigame.label}
        </p>
        <p className="truncate text-xs text-zinc-500">
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
