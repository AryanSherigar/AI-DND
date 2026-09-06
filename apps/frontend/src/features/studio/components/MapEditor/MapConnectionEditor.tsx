import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import { useEntities } from "../../hooks/useEntities";
import { useMapConnections } from "../../hooks/useMapConnections";
import { MapConnectionEditorProps } from "./MapEditor.types";

export const MapConnectionEditor: React.FC<MapConnectionEditorProps> = ({
  scenarioId,
}) => {
  const { entities } = useEntities(scenarioId);
  const { connections, createConnection, deleteConnection, createError } =
    useMapConnections(scenarioId);
  const [entityIdA, setEntityIdA] = useState("");
  const [entityIdB, setEntityIdB] = useState("");
  const [label, setLabel] = useState("");

  const locationEntities = entities.filter((e) => e.entity_type === "location");
  const entityName = (entityId: string): string =>
    entities.find((e) => e.entity_id === entityId)?.canonical_name ?? entityId;

  const handleCreate = (): void => {
    if (!entityIdA || !entityIdB || entityIdA === entityIdB) return;
    createConnection(
      { entity_id_a: entityIdA, entity_id_b: entityIdB, label: label || null },
      { onSuccess: () => setLabel("") },
    );
  };

  const locationOptions = [
    { value: "", label: "Choose a location…" },
    ...locationEntities.map((e) => ({
      value: e.entity_id,
      label: e.canonical_name,
    })),
  ];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-content">Connections</h2>
        <p className="mt-1 text-xs text-content-faint">
          Connections may cross maps and are advisory only — they hint the
          narrator with known paths but never restrict where the player can go.
        </p>
      </div>
      {locationEntities.length < 2 ? (
        <EmptyState
          title="Add at least two Location entities"
          description="Connections link two Location entities together, wherever they're pinned."
        />
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <Select
            value={entityIdA}
            onChange={(e) => setEntityIdA(e.target.value)}
            options={locationOptions}
          />
          <Select
            value={entityIdB}
            onChange={(e) => setEntityIdB(e.target.value)}
            options={locationOptions}
          />
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Optional description (e.g. a muddy trail)"
          />
          <Button
            size="sm"
            onClick={handleCreate}
            disabled={!entityIdA || !entityIdB || entityIdA === entityIdB}
          >
            Connect
          </Button>
        </div>
      )}
      {createError && <p className="text-xs text-danger">{createError}</p>}
      <div className="space-y-1">
        {connections.map((connection) => (
          <div
            key={connection.connection_id}
            className="rounded-md flex items-center justify-between border border-border-subtle px-3 py-1.5 text-xs"
          >
            <span className="text-content-muted">
              {entityName(connection.entity_id_a)} ↔{" "}
              {entityName(connection.entity_id_b)}
              {connection.label && (
                <span className="ml-2 text-content-faint">({connection.label})</span>
              )}
            </span>
            <button
              onClick={() => deleteConnection(connection.connection_id)}
              className="text-content-faint hover:text-danger"
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
