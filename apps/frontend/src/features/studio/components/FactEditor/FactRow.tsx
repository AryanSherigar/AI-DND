import React from "react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { FactRowProps } from "./FactRow.types";

const resolveObjectLabel = (
  fact: FactRowProps["fact"],
  entityById: FactRowProps["entityById"],
): string => {
  if (fact.object_entity_id) {
    return (
      entityById.get(fact.object_entity_id)?.canonical_name ??
      fact.object_entity_id
    );
  }
  return fact.object_literal ?? "";
};

export const FactRow: React.FC<FactRowProps> = ({
  fact,
  entityById,
  onDelete,
}) => {
  const subjectEntity = entityById.get(fact.subject_entity_id);
  const isSubjectMissing = !subjectEntity;
  const isObjectMissing =
    Boolean(fact.object_entity_id) &&
    !entityById.get(fact.object_entity_id as string);
  const objectLabel = resolveObjectLabel(fact, entityById);

  const handleDeleteClick = (): void => onDelete(fact.fact_id);

  return (
    <div className="border border-zinc-800 bg-zinc-900 px-3 py-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-zinc-200">
          {subjectEntity?.canonical_name ?? fact.subject_entity_id} →{" "}
          {fact.predicate} → {objectLabel}
        </span>
        <div className="flex items-center gap-2">
          {fact.hidden && <Badge variant="warning">Hidden</Badge>}
          <Button
            type="button"
            variant="danger"
            size="sm"
            onClick={handleDeleteClick}
          >
            Delete
          </Button>
        </div>
      </div>
      {isSubjectMissing && (
        <p className="mt-1 text-xs text-red-400">
          Subject: this entity no longer exists.
        </p>
      )}
      {isObjectMissing && (
        <p className="mt-1 text-xs text-red-400">
          Object: this entity no longer exists.
        </p>
      )}
    </div>
  );
};
