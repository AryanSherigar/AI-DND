import React from "react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { ExpandablePanel } from "@/shared/components/ui/ExpandablePanel";
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
  onEdit,
  onDelete,
}) => {
  const subjectEntity = entityById.get(fact.subject_entity_id);
  const isSubjectMissing = !subjectEntity;
  const isObjectMissing =
    Boolean(fact.object_entity_id) &&
    !entityById.get(fact.object_entity_id as string);
  const objectLabel = resolveObjectLabel(fact, entityById);

  const handleEditClick = (): void => onEdit(fact);
  const handleDeleteClick = (): void => onDelete(fact.fact_id);

  const summary = (
    <span className="flex items-center gap-2">
      <span className="text-sm text-zinc-200">
        {subjectEntity?.canonical_name ?? fact.subject_entity_id} →{" "}
        {fact.predicate} → {objectLabel}
      </span>
      {fact.hidden && <Badge variant="warning">Hidden</Badge>}
    </span>
  );

  const actions = (
    <>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={handleEditClick}
      >
        Edit
      </Button>
      <Button
        type="button"
        variant="danger"
        size="sm"
        onClick={handleDeleteClick}
      >
        Delete
      </Button>
    </>
  );

  return (
    <div>
      <ExpandablePanel summary={summary} actions={actions}>
        <div className="space-y-1 text-xs text-zinc-500">
          <p>Valid from: {fact.valid_from ?? "always"}</p>
          <p>
            Active when:{" "}
            {fact.when_active
              ? JSON.stringify(fact.when_active)
              : "always active"}
          </p>
          {fact.superseded_fact_id && (
            <p>Supersedes fact: {fact.superseded_fact_id}</p>
          )}
        </div>
      </ExpandablePanel>
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
