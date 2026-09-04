import React, { useMemo, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Modal } from "@/shared/components/ui/Modal";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import { useEntities } from "../../hooks/useEntities";
import { useFacts } from "../../hooks/useFacts";
import { useStudioStore } from "../../stores/studio.store";
import { EntityResponse } from "../../types/entity.types";
import { FactCreate, FactResponse, FactUpdate } from "../../types/fact.types";
import { FactEditorProps } from "./FactEditor.types";
import { FactForm } from "./FactForm";
import { FactRow } from "./FactRow";

const ALL_ENTITIES_OPTION: SelectOption = { value: "", label: "All entities" };

const buildEntityById = (
  entities: EntityResponse[],
): Map<string, EntityResponse> => {
  const map = new Map<string, EntityResponse>();
  entities.forEach((entity) => map.set(entity.entity_id, entity));
  return map;
};

export const FactEditor: React.FC<FactEditorProps> = ({ scenarioId }) => {
  const { entities } = useEntities(scenarioId);
  const entityFilter = useStudioStore((state) => state.factsEntityFilter);
  const setEntityFilter = useStudioStore((state) => state.setFactsEntityFilter);
  const {
    facts,
    isLoading,
    createFact,
    updateFact,
    deleteFact,
    isCreating,
    isUpdating,
    createError,
    updateError,
  } = useFacts(scenarioId, entityFilter);
  const [editingFact, setEditingFact] = useState<FactResponse | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);

  const entityById = useMemo(() => buildEntityById(entities), [entities]);
  const entityFilterOptions: SelectOption[] = useMemo(
    () => [
      ALL_ENTITIES_OPTION,
      ...entities.map((entity) => ({
        value: entity.entity_id,
        label: entity.canonical_name,
      })),
    ],
    [entities],
  );

  const handleFilterChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ): void => setEntityFilter(event.target.value || null);

  const handleOpenCreate = (): void => {
    setEditingFact(null);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (fact: FactResponse): void => {
    setEditingFact(fact);
    setIsFormOpen(true);
  };

  const handleCloseForm = (): void => setIsFormOpen(false);
  const handleDelete = (factId: string): void => deleteFact(factId);

  const handleSubmit = (payload: FactCreate): void => {
    if (editingFact) {
      const updatePayload: FactUpdate = payload;
      updateFact(
        { factId: editingFact.fact_id, payload: updatePayload },
        { onSuccess: handleCloseForm },
      );
      return;
    }
    createFact(payload, { onSuccess: handleCloseForm });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Facts</h1>
        <Button onClick={handleOpenCreate}>New Fact</Button>
      </div>
      <div className="flex items-center gap-2">
        <Select
          aria-label="Filter by entity"
          options={entityFilterOptions}
          value={entityFilter ?? ""}
          onChange={handleFilterChange}
          className="max-w-xs"
        />
        {entityFilter && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setEntityFilter(null)}
          >
            Clear filter
          </Button>
        )}
      </div>
      {isLoading && <p className="text-sm text-zinc-500">Loading facts…</p>}
      {!isLoading && facts.length === 0 && (
        <EmptyState
          title="No facts yet"
          description="Facts are statements the narrator checks and respects during play. They can link two entities, or attach a standalone note."
          example="Example: Hero → owns → Sword"
        />
      )}
      <div className="space-y-2">
        {facts.map((fact) => (
          <FactRow
            key={fact.fact_id}
            fact={fact}
            entityById={entityById}
            onEdit={handleOpenEdit}
            onDelete={handleDelete}
          />
        ))}
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        title={editingFact ? "Edit Fact" : "New Fact"}
      >
        <FactForm
          entities={entities}
          fact={editingFact}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating || isUpdating}
          submitError={editingFact ? updateError : createError}
        />
      </Modal>
    </div>
  );
};
