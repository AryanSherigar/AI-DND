import React, { useMemo, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Modal } from "@/shared/components/ui/Modal";
import { useEntities } from "../../hooks/useEntities";
import { useFacts } from "../../hooks/useFacts";
import { EntityResponse } from "../../types/entity.types";
import { FactCreate } from "../../types/fact.types";
import { FactEditorProps } from "./FactEditor.types";
import { FactForm } from "./FactForm";
import { FactRow } from "./FactRow";

const buildEntityById = (
  entities: EntityResponse[],
): Map<string, EntityResponse> => {
  const map = new Map<string, EntityResponse>();
  entities.forEach((entity) => map.set(entity.entity_id, entity));
  return map;
};

export const FactEditor: React.FC<FactEditorProps> = ({ scenarioId }) => {
  const { entities } = useEntities(scenarioId);
  const { facts, isLoading, createFact, deleteFact, isCreating, createError } =
    useFacts(scenarioId);
  const [isFormOpen, setIsFormOpen] = useState(false);

  const entityById = useMemo(() => buildEntityById(entities), [entities]);

  const handleOpenCreate = (): void => setIsFormOpen(true);
  const handleCloseForm = (): void => setIsFormOpen(false);
  const handleDelete = (factId: string): void => deleteFact(factId);

  const handleSubmit = (payload: FactCreate): void => {
    createFact(payload, { onSuccess: handleCloseForm });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Facts</h1>
        <Button onClick={handleOpenCreate}>New Fact</Button>
      </div>
      {isLoading && <p className="text-sm text-zinc-500">Loading facts…</p>}
      <div className="space-y-2">
        {facts.map((fact) => (
          <FactRow
            key={fact.fact_id}
            fact={fact}
            entityById={entityById}
            onDelete={handleDelete}
          />
        ))}
      </div>
      <Modal isOpen={isFormOpen} onClose={handleCloseForm} title="New Fact">
        <FactForm
          entities={entities}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating}
          submitError={createError}
        />
      </Modal>
    </div>
  );
};
