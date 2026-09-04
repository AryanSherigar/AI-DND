import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { Modal } from "@/shared/components/ui/Modal";
import { EntityTypeChangeWarningModalProps } from "./EntityTypeChangeWarningModal.types";

export const EntityTypeChangeWarningModal: React.FC<
  EntityTypeChangeWarningModalProps
> = ({ isOpen, newTypeLabel, preview, onConfirm, onCancel }) => {
  const droppedFields = preview?.dropped_fields ?? [];
  const addedFields = preview?.added_fields ?? [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onCancel}
      title={`Change type to ${newTypeLabel}?`}
    >
      <div className="space-y-3 text-sm text-zinc-300">
        {droppedFields.length > 0 && (
          <p>
            These attributes don't belong to {newTypeLabel}'s template and won't
            be removed automatically, but they won't match it either:{" "}
            <span className="text-amber-400">{droppedFields.join(", ")}</span>
          </p>
        )}
        {addedFields.length > 0 && (
          <p>
            {newTypeLabel} also defines attributes this entity doesn't have yet:{" "}
            <span className="text-zinc-400">{addedFields.join(", ")}</span>
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" onClick={onConfirm}>
            Confirm change
          </Button>
        </div>
      </div>
    </Modal>
  );
};
