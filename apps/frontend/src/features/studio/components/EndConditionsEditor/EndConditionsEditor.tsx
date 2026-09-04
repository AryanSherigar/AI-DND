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
import { useEndConditions } from "../../hooks/useEndConditions";
import { useEntities } from "../../hooks/useEntities";
import { useScenario } from "../../hooks/useScenario";
import {
  EndConditionCreate,
  EndConditionResponse,
  EndConditionUpdate,
} from "../../types/end_condition.types";
import { buildAvailableFields } from "../ConditionEditor/ExpressionBuilder/availableFields";
import { EndConditionForm } from "./EndConditionForm";
import { EndConditionRow } from "./EndConditionRow";
import { EndConditionsEditorProps } from "./EndConditionsEditor.types";
import { buildReorderedIds, sortByPriority } from "./endConditionOrdering";

export const EndConditionsEditor: React.FC<EndConditionsEditorProps> = ({
  scenarioId,
}) => {
  const { scenario } = useScenario(scenarioId);
  const { entities } = useEntities(scenarioId);
  const {
    endConditions,
    isLoading,
    createEndCondition,
    updateEndCondition,
    deleteEndCondition,
    reorderEndConditions,
    isCreating,
    isUpdating,
    createError,
    updateError,
  } = useEndConditions(scenarioId);
  const [editingEndCondition, setEditingEndCondition] =
    useState<EndConditionResponse | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor));

  const orderedEndConditions = useMemo(
    () => sortByPriority(endConditions),
    [endConditions],
  );

  const availableFields = useMemo(
    () => buildAvailableFields(scenario?.state_schema ?? {}, entities),
    [scenario, entities],
  );

  const handleOpenCreate = (): void => {
    setEditingEndCondition(null);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (endCondition: EndConditionResponse): void => {
    setEditingEndCondition(endCondition);
    setIsFormOpen(true);
  };

  const handleCloseForm = (): void => setIsFormOpen(false);
  const handleDelete = (endConditionId: string): void =>
    deleteEndCondition(endConditionId);

  const handleSubmit = (payload: EndConditionCreate): void => {
    if (editingEndCondition) {
      const updatePayload: EndConditionUpdate = payload;
      updateEndCondition(
        {
          endConditionId: editingEndCondition.end_condition_id,
          payload: updatePayload,
        },
        { onSuccess: handleCloseForm },
      );
      return;
    }
    createEndCondition(payload, { onSuccess: handleCloseForm });
  };

  const handleDragEnd = (event: DragEndEvent): void => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const reorderedIds = buildReorderedIds(
      orderedEndConditions,
      String(active.id),
      String(over.id),
    );
    reorderEndConditions(reorderedIds);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Endings</h1>
        <Button onClick={handleOpenCreate}>New End Condition</Button>
      </div>
      {isLoading && (
        <p className="text-sm text-zinc-500">Loading end conditions…</p>
      )}
      {!isLoading && orderedEndConditions.length === 0 && (
        <EmptyState
          title="No win or lose conditions yet"
          description="End conditions define how a playthrough concludes, with an outcome, a message shown to the player, and an optional trigger."
          example="Example: outcome_tag = win when party.gold >= 1000"
        />
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={orderedEndConditions.map((item) => item.end_condition_id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {orderedEndConditions.map((endCondition) => (
              <EndConditionRow
                key={endCondition.end_condition_id}
                endCondition={endCondition}
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
        title={editingEndCondition ? "Edit End Condition" : "New End Condition"}
      >
        <EndConditionForm
          availableFields={availableFields}
          endCondition={editingEndCondition}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating || isUpdating}
          submitError={editingEndCondition ? updateError : createError}
        />
      </Modal>
    </div>
  );
};
