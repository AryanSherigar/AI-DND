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
import { Modal } from "@/shared/components/ui/Modal";
import { useEndConditions } from "../../hooks/useEndConditions";
import { useEntities } from "../../hooks/useEntities";
import { useScenario } from "../../hooks/useScenario";
import { EndConditionCreate } from "../../types/end_condition.types";
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
    deleteEndCondition,
    reorderEndConditions,
    isCreating,
    createError,
  } = useEndConditions(scenarioId);
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

  const handleOpenCreate = (): void => setIsFormOpen(true);
  const handleCloseForm = (): void => setIsFormOpen(false);
  const handleDelete = (endConditionId: string): void =>
    deleteEndCondition(endConditionId);

  const handleSubmit = (payload: EndConditionCreate): void => {
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
                onDelete={handleDelete}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        title="New End Condition"
      >
        <EndConditionForm
          availableFields={availableFields}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating}
          submitError={createError}
        />
      </Modal>
    </div>
  );
};
