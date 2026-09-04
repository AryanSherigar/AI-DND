import React, { useState } from "react";
import { MapConnection, MapPin, ScenarioMap } from "@/shared/types/map.types";
import { MapViewerProps } from "./MapViewer.types";

interface SnapshotEntity {
  entity_id: string;
  canonical_name?: string;
}

/**
 * Read-only fog-of-war map viewer: shows only discovered pins/connections on
 * whichever map contains the player's current location. Purely a viewer — no
 * click-to-travel, per the locked "movement is text-driven only" decision
 * (docs/specs/master-mode-maps.spec.md). Renders nothing for scenarios
 * without maps, so it's a no-op to mount on every playthrough page.
 */
export const MapViewer: React.FC<MapViewerProps> = ({
  scenarioSnapshot,
  state,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const maps = (scenarioSnapshot?.maps as ScenarioMap[] | undefined) ?? [];
  const pins = (scenarioSnapshot?.map_pins as MapPin[] | undefined) ?? [];
  const connections =
    (scenarioSnapshot?.map_connections as MapConnection[] | undefined) ?? [];
  const entities =
    (scenarioSnapshot?.entities as SnapshotEntity[] | undefined) ?? [];

  if (maps.length === 0) return null;

  const currentLocationId = state?.current_location_id as string | undefined;
  const discoveredIds = new Set(
    (state?.discovered_location_ids as string[] | undefined) ?? [],
  );

  const activeMap =
    maps.find((m) =>
      pins.some(
        (p) => p.map_id === m.map_id && p.entity_id === currentLocationId,
      ),
    ) ?? maps[0];

  const visiblePins = pins.filter(
    (p) => p.map_id === activeMap.map_id && discoveredIds.has(p.entity_id),
  );
  const visibleEntityIds = new Set(visiblePins.map((p) => p.entity_id));
  const visibleConnections = connections.filter(
    (c) =>
      visibleEntityIds.has(c.entity_id_a) &&
      visibleEntityIds.has(c.entity_id_b),
  );

  const entityName = (entityId: string): string =>
    entities.find((e) => e.entity_id === entityId)?.canonical_name ?? entityId;
  const pinByEntity = (entityId: string): MapPin | undefined =>
    visiblePins.find((p) => p.entity_id === entityId);

  return (
    <div className="fixed bottom-4 right-4 z-20 w-72 border border-zinc-800 bg-zinc-950/95 font-sans text-zinc-300 shadow-xl">
      <button
        onClick={() => setIsCollapsed((c) => !c)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-semibold text-zinc-100"
      >
        <span>{activeMap.name}</span>
        <span className="text-zinc-500">{isCollapsed ? "Show" : "Hide"}</span>
      </button>
      {!isCollapsed && (
        <div className="border-t border-zinc-800 p-2">
          {!activeMap.image_url || visiblePins.length === 0 ? (
            <p className="p-2 text-xs text-zinc-500">
              Nothing discovered on this map yet.
            </p>
          ) : (
            <div className="relative w-full" style={{ aspectRatio: "16 / 9" }}>
              <img
                src={activeMap.image_url}
                alt={activeMap.name}
                className="absolute inset-0 h-full w-full object-cover"
              />
              <svg className="absolute inset-0 h-full w-full">
                {visibleConnections.map((connection) => {
                  const a = pinByEntity(connection.entity_id_a);
                  const b = pinByEntity(connection.entity_id_b);
                  if (!a || !b) return null;
                  return (
                    <line
                      key={connection.connection_id}
                      x1={`${a.x * 100}%`}
                      y1={`${a.y * 100}%`}
                      x2={`${b.x * 100}%`}
                      y2={`${b.y * 100}%`}
                      stroke="rgb(212 212 216 / 0.5)"
                      strokeWidth={1}
                    />
                  );
                })}
              </svg>
              {visiblePins.map((pin) => (
                <div
                  key={pin.pin_id}
                  title={entityName(pin.entity_id)}
                  className={`absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap border px-1.5 py-0.5 text-[10px] ${
                    pin.entity_id === currentLocationId
                      ? "border-amber-400 bg-amber-950 text-amber-200"
                      : "border-zinc-500 bg-zinc-900 text-zinc-300"
                  }`}
                  style={{ left: `${pin.x * 100}%`, top: `${pin.y * 100}%` }}
                >
                  {entityName(pin.entity_id)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
