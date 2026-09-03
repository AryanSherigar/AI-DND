import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Modal } from "@/shared/components/ui/Modal";
import { useEntities } from "../../hooks/useEntities";
import {
  EntityCreate,
  EntityResponse,
  EntityUpdate,
} from "../../types/entity.types";
import { EntityEditorProps } from "./EntityEditor.types";
import { EntityForm } from "./EntityForm";
import { EntityRow } from "./EntityRow";

export const EntityEditor: React.FC<EntityEditorProps> = ({ scenarioId }) => {
  const {
    entities,
    isLoading,
    createEntity,
    updateEntity,
    deleteEntity,
    isCreating,
    isUpdating,
    createError,
    updateError,
  } = useEntities(scenarioId);
  const [editingEntity, setEditingEntity] = useState<EntityResponse | null>(
    null,
  );
  const [isFormOpen, setIsFormOpen] = useState(false);

  const handleOpenCreate = (): void => {
    setEditingEntity(null);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (entity: EntityResponse): void => {
    setEditingEntity(entity);
    setIsFormOpen(true);
  };

  const handleCloseForm = (): void => setIsFormOpen(false);

  const handleDelete = (entityId: string): void => deleteEntity(entityId);

  const handleSubmit = (payload: EntityCreate): void => {
    if (editingEntity) {
      const updatePayload: EntityUpdate = payload;
      updateEntity(
        { entityId: editingEntity.entity_id, payload: updatePayload },
        { onSuccess: handleCloseForm },
      );
      return;
    }
    createEntity(payload, { onSuccess: handleCloseForm });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Entities</h1>
        <Button onClick={handleOpenCreate}>New Entity</Button>
      </div>
      {isLoading && <p className="text-sm text-zinc-500">Loading entities…</p>}
      <div className="space-y-2">
        {entities.map((entity) => (
          <EntityRow
            key={entity.entity_id}
            entity={entity}
            onEdit={handleOpenEdit}
            onDelete={handleDelete}
          />
        ))}
      </div>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        title={editingEntity ? "Edit Entity" : "New Entity"}
      >
        <EntityForm
          entity={editingEntity}
          onSubmit={handleSubmit}
          onCancel={handleCloseForm}
          isSubmitting={isCreating || isUpdating}
          submitError={editingEntity ? updateError : createError}
        />
      </Modal>
    </div>
  );
};
