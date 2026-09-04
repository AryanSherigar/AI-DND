import React, { useMemo, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Modal } from "@/shared/components/ui/Modal";
import { SelectOption } from "@/shared/components/ui/Select";
import { buildAvailableFields } from "../ConditionEditor/ExpressionBuilder/availableFields";
import { useEntities } from "../../hooks/useEntities";
import { useInvariants } from "../../hooks/useInvariants";
import { useScenario } from "../../hooks/useScenario";
import {
  InvariantCreate,
  InvariantResponse,
  InvariantUpdate,
} from "../../types/invariant.types";
import { InvariantEditorProps } from "./InvariantEditor.types";
import { InvariantForm } from "./InvariantForm";
import { InvariantRow } from "./InvariantRow";

const FIXED_APPLIES_TO_OPTIONS: SelectOption[] = [
  { value: "global", label: "Global" },
  { value: "player", label: "Player" },
];

export const InvariantEditor: React.FC<InvariantEditorProps> = ({
  scenarioId,
}) => {
  const {
    invariants,
    isLoading,
    createInvariant,
    updateInvariant,
    deleteInvariant,
    isCreating,
    isUpdating,
    createError,
    updateError,
  } = useInvariants(scenarioId);
  const { scenario } = useScenario(scenarioId);
  const { entities } = useEntities(scenarioId);
  const [editingInvariant, setEditingInvariant] =
    useState<InvariantResponse | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);

  const availableFields = useMemo(
    () => buildAvailableFields(scenario?.state_schema ?? {}, entities),
    [scenario, entities],
  );

  const appliesToOptions = useMemo<SelectOption[]>(
    () => [
      ...FIXED_APPLIES_TO_OPTIONS,
      ...entities.map((entity) => ({
        value: entity.entity_id,
        label: entity.canonical_name,
      })),
    ],
    [entities],
  );

  const handleOpenCreate = (): void => {
    setEditingInvariant(null);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (invariant: InvariantResponse): void => {
    setEditingInvariant(invariant);
    setIsFormOpen(true);
  };

  const handleCloseForm = (): void => setIsFormOpen(false);

  const handleDelete = (invariantId: string): void =>
    deleteInvariant(invariantId);

  const handleSubmit = (payload: InvariantCreate): void => {
    if (editingInvariant) {
      const updatePayload: InvariantUpdate = payload;
      updateInvariant(
        { invariantId: editingInvariant.invariant_id, payload: updatePayload },
        { onSuccess: handleCloseForm },
      );
      return;
    }
    createInvariant(payload, { onSuccess: handleCloseForm });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">World Rules</h1>
        <Button onClick={handleOpenCreate}>New Invariant</Button>
      </div>
      {isLoading && (
        <p className="text-sm text-zinc-500">Loading invariants…</p>
      )}
      {!isLoading && invariants.length === 0 && (
        <EmptyState
          title="No always-true rules yet"
          description="Always-true rules are constraints the narrator must never violate, regardless of what else happens in the story."
          example="Example: the player character can never die permanently."
        />
      )}
      <div className="space-y-2">
        {invariants.map((invariant) => (
          <InvariantRow
            key={invariant.invariant_id}
            invariant={invariant}
            onEdit={handleOpenEdit}
            onDelete={handleDelete}
          />
        ))}
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        title={editingInvariant ? "Edit Invariant" : "New Invariant"}
      >
        <InvariantForm
          invariant={editingInvariant}
          availableFields={availableFields}
          appliesToOptions={appliesToOptions}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating || isUpdating}
          submitError={editingInvariant ? updateError : createError}
        />
      </Modal>
    </div>
  );
};
