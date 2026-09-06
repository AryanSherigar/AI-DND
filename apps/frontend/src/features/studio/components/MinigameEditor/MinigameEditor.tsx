import React, { useMemo, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Button } from "@/shared/components/ui/Button";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Modal } from "@/shared/components/ui/Modal";
import { useEntities } from "../../hooks/useEntities";
import { useMinigames } from "../../hooks/useMinigames";
import { useScenario } from "../../hooks/useScenario";
import {
  MinigameCreate,
  MinigameResponse,
  MinigameUpdate,
} from "../../types/minigame.types";
import { buildAvailableFields } from "../ConditionEditor/ExpressionBuilder/availableFields";
import { MinigameEditorProps } from "./MinigameEditor.types";
import { MinigameForm } from "./MinigameForm";
import { MinigameRow } from "./MinigameRow";
import { buildReorderedIds, sortByPriority } from "./minigameOrdering";

export const MinigameEditor: React.FC<MinigameEditorProps> = ({
  scenarioId,
}) => {
  const { scenario } = useScenario(scenarioId);
  const { entities } = useEntities(scenarioId);
  const {
    minigames,
    isLoading,
    createMinigame,
    updateMinigame,
    deleteMinigame,
    reorderMinigames,
    isCreating,
    isUpdating,
    createError,
    updateError,
  } = useMinigames(scenarioId);
  const [editingMinigame, setEditingMinigame] =
    useState<MinigameResponse | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor));

  const orderedMinigames = useMemo(
    () => sortByPriority(minigames),
    [minigames],
  );

  const availableFields = useMemo(
    () => buildAvailableFields(scenario?.state_schema ?? {}, entities),
    [scenario, entities],
  );

  const handleOpenCreate = (): void => {
    setEditingMinigame(null);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (minigame: MinigameResponse): void => {
    setEditingMinigame(minigame);
    setIsFormOpen(true);
  };

  const handleCloseForm = (): void => setIsFormOpen(false);
  const handleDelete = (minigameId: string): void => deleteMinigame(minigameId);

  const handleSubmit = (payload: MinigameCreate): void => {
    if (editingMinigame) {
      const updatePayload: MinigameUpdate = payload;
      updateMinigame(
        { minigameId: editingMinigame.minigame_id, payload: updatePayload },
        { onSuccess: handleCloseForm },
      );
      return;
    }
    createMinigame(payload, { onSuccess: handleCloseForm });
  };

  const handleDragEnd = (event: DragEndEvent): void => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const reorderedIds = buildReorderedIds(
      orderedMinigames,
      String(active.id),
      String(over.id),
    );
    reorderMinigames(reorderedIds);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Minigames</h1>
        <Button onClick={handleOpenCreate}>New Minigame</Button>
      </div>
      {isLoading && <p className="text-sm text-zinc-500">Loading minigames…</p>}
      {!isLoading && orderedMinigames.length === 0 && (
        <EmptyState
          title="No minigames yet"
          description="Minigames trigger a full-screen interstitial challenge — a curated dodge arena or your own Replit-hosted game — whose outcome mutates state and feeds back into the narration."
          example="Example: trigger the Ashfall Dodge challenge when the player enters the ambush clearing"
        />
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={orderedMinigames.map((item) => item.minigame_id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {orderedMinigames.map((minigame) => (
              <MinigameRow
                key={minigame.minigame_id}
                minigame={minigame}
                onEdit={handleOpenEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        title={editingMinigame ? "Edit Minigame" : "New Minigame"}
      >
        <MinigameForm
          availableFields={availableFields}
          minigame={editingMinigame}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating || isUpdating}
          submitError={editingMinigame ? updateError : createError}
        />
      </Modal>
    </div>
  );
};
