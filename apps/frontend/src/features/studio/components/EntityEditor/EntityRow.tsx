import React from "react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { ExpandablePanel } from "@/shared/components/ui/ExpandablePanel";
import { useStudioStore } from "../../stores/studio.store";
import { EntityRowProps } from "./EntityRow.types";

const ENTITY_TYPE_LABEL: Record<string, string> = {
  character: "Character",
  location: "Location",
  item: "Item",
  faction: "Faction",
  organization: "Organization",
};

const resolveTypeLabel = (entityType: string): string =>
  ENTITY_TYPE_LABEL[entityType] ?? entityType;

const truncate = (text: string, maxLength: number): string =>
  text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;

export const EntityRow: React.FC<EntityRowProps> = ({
  entity,
  onEdit,
  onDelete,
}) => {
  const attributeEntries = Object.entries(entity.attributes_schema);
  const factCount = entity.fact_count ?? 0;
  const setActiveMasterTab = useStudioStore(
    (state) => state.setActiveMasterTab,
  );
  const setFactsEntityFilter = useStudioStore(
    (state) => state.setFactsEntityFilter,
  );
  const handleEditClick = (): void => onEdit(entity);
  const handleDeleteClick = (): void => onDelete(entity.entity_id);
  const handleViewFactsClick = (): void => {
    setFactsEntityFilter(entity.entity_id);
    setActiveMasterTab("facts");
  };

  const summary = (
    <span className="flex items-center gap-2">
      <span className="text-sm text-zinc-200">{entity.canonical_name}</span>
      <Badge>{resolveTypeLabel(entity.entity_type)}</Badge>
      {entity.description && (
        <span className="truncate text-xs text-zinc-500">
          {truncate(entity.description, 80)}
        </span>
      )}
      <span className="text-xs text-zinc-600">
        {factCount} fact{factCount === 1 ? "" : "s"}
      </span>
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
    <ExpandablePanel summary={summary} actions={actions}>
      <div className="space-y-3 text-sm">
        {entity.description && (
          <p className="text-zinc-300">{entity.description}</p>
        )}
        {entity.aliases.length > 0 && (
          <p className="text-xs text-zinc-500">
            Aliases: {entity.aliases.join(", ")}
          </p>
        )}
        {entity.obtainable !== null && (
          <p className="text-xs text-zinc-500">
            Obtainable: {entity.obtainable ? "Yes" : "No"}
          </p>
        )}
        {entity.narrator_instruction && (
          <p className="text-xs text-zinc-500">
            Narrator instruction: {entity.narrator_instruction}
          </p>
        )}
        <button
          type="button"
          onClick={handleViewFactsClick}
          className="text-xs text-zinc-400 underline hover:text-zinc-200"
        >
          View {factCount} related fact{factCount === 1 ? "" : "s"} →
        </button>
        <div>
          <p className="text-xs font-medium text-zinc-400">Attributes</p>
          {attributeEntries.length === 0 ? (
            <p className="text-xs text-zinc-600">No attributes defined.</p>
          ) : (
            <table className="mt-1 w-full text-xs text-zinc-400">
              <tbody>
                {attributeEntries.map(([key, schema]) => (
                  <tr key={key} className="border-t border-zinc-800">
                    <td className="py-1 pr-3 font-medium text-zinc-300">
                      {schema.label ?? key}
                    </td>
                    <td className="py-1 pr-3">{schema.type}</td>
                    <td className="py-1 text-zinc-500">
                      {schema.initial !== undefined
                        ? `initial: ${String(schema.initial)}`
                        : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </ExpandablePanel>
  );
};
