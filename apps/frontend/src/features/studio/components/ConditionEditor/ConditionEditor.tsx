import React, { useMemo, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Modal } from "@/shared/components/ui/Modal";
import { useConditions } from "../../hooks/useConditions";
import { useEntities } from "../../hooks/useEntities";
import { useScenario } from "../../hooks/useScenario";
import {
  ConditionCreate,
  ConditionResponse,
  ConditionUpdate,
} from "../../types/condition.types";
import { buildAvailableFields } from "./ExpressionBuilder/availableFields";
import { ConditionEditorProps } from "./ConditionEditor.types";
import { ConditionForm } from "./ConditionForm";
import { ConditionRow } from "./ConditionRow";

export const ConditionEditor: React.FC<ConditionEditorProps> = ({
  scenarioId,
}) => {
  const {
    conditions,
    isLoading,
    createCondition,
    updateCondition,
    deleteCondition,
    isCreating,
    isUpdating,
    createError,
    updateError,
  } = useConditions(scenarioId);
  const { scenario } = useScenario(scenarioId);
  const { entities } = useEntities(scenarioId);
  const [editingCondition, setEditingCondition] =
    useState<ConditionResponse | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);

  const availableFields = useMemo(
    () => buildAvailableFields(scenario?.state_schema ?? {}, entities),
    [scenario, entities],
  );

  const handleOpenCreate = (): void => {
    setEditingCondition(null);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (condition: ConditionResponse): void => {
    setEditingCondition(condition);
    setIsFormOpen(true);
  };

  const handleCloseForm = (): void => setIsFormOpen(false);

  const handleDelete = (conditionId: string): void =>
    deleteCondition(conditionId);

  const handleSubmit = (payload: ConditionCreate): void => {
    if (editingCondition) {
      const updatePayload: ConditionUpdate = payload;
      updateCondition(
        { conditionId: editingCondition.condition_id, payload: updatePayload },
        { onSuccess: handleCloseForm },
      );
      return;
    }
    createCondition(payload, { onSuccess: handleCloseForm });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">
          Active Conditions
        </h1>
        <Button onClick={handleOpenCreate}>New Condition</Button>
      </div>
      {isLoading && (
        <p className="text-sm text-zinc-500">Loading conditions…</p>
      )}
      <div className="space-y-2">
        {conditions.map((condition) => (
          <ConditionRow
            key={condition.condition_id}
            condition={condition}
            onEdit={handleOpenEdit}
            onDelete={handleDelete}
          />
        ))}
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        title={editingCondition ? "Edit Condition" : "New Condition"}
      >
        <ConditionForm
          condition={editingCondition}
          availableFields={availableFields}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating || isUpdating}
          submitError={editingCondition ? updateError : createError}
        />
      </Modal>
    </div>
  );
};
