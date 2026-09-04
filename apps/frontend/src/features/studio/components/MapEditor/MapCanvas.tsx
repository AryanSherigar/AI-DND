import React, { useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Select } from "@/shared/components/ui/Select";
import { useEntities } from "../../hooks/useEntities";
import { useMapPins } from "../../hooks/useMapPins";
import { useMaps } from "../../hooks/useMaps";
import { MapPin } from "@/shared/types/map.types";
import { MapCanvasProps } from "./MapEditor.types";

interface PendingPin {
  x: number;
  y: number;
}

export const MapCanvas: React.FC<MapCanvasProps> = ({ scenarioId, mapId }) => {
  const { maps } = useMaps(scenarioId);
  const { entities } = useEntities(scenarioId);
  const { pins, createPin, updatePin, deletePin, createError } = useMapPins(
    scenarioId,
    mapId,
  );
  const canvasRef = useRef<HTMLDivElement>(null);
  const [pendingPin, setPendingPin] = useState<PendingPin | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState("");
  const [draggingPinId, setDraggingPinId] = useState<string | null>(null);

  const map = maps.find((m) => m.map_id === mapId);
  const pinnedEntityIds = new Set(pins.map((p) => p.entity_id));
  const availableLocationEntities = entities.filter(
    (e) => e.entity_type === "location" && !pinnedEntityIds.has(e.entity_id),
  );
  const entityName = (entityId: string): string =>
    entities.find((e) => e.entity_id === entityId)?.canonical_name ?? entityId;

  const relativeCoords = (
    event: React.MouseEvent | MouseEvent,
  ): PendingPin | null => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return {
      x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
    };
  };

  const handleCanvasClick = (event: React.MouseEvent<HTMLDivElement>): void => {
    if (event.target !== event.currentTarget || draggingPinId) return;
    const coords = relativeCoords(event);
    if (!coords) return;
    setPendingPin(coords);
    setSelectedEntityId("");
  };

  const handlePlacePin = (): void => {
    if (!pendingPin || !selectedEntityId) return;
    createPin({
      entity_id: selectedEntityId,
      x: pendingPin.x,
      y: pendingPin.y,
    });
    setPendingPin(null);
  };

  const handlePinPointerDown =
    (pinId: string) =>
    (event: React.PointerEvent<HTMLButtonElement>): void => {
      event.stopPropagation();
      event.currentTarget.setPointerCapture(event.pointerId);
      setDraggingPinId(pinId);
    };

  const handlePinPointerMove =
    (pin: MapPin) =>
    (event: React.PointerEvent<HTMLButtonElement>): void => {
      if (draggingPinId !== pin.pin_id) return;
      const coords = relativeCoords(event);
      if (!coords) return;
      event.currentTarget.style.left = `${coords.x * 100}%`;
      event.currentTarget.style.top = `${coords.y * 100}%`;
    };

  const handlePinPointerUp =
    (pin: MapPin) =>
    (event: React.PointerEvent<HTMLButtonElement>): void => {
      if (draggingPinId !== pin.pin_id) return;
      const coords = relativeCoords(event);
      setDraggingPinId(null);
      if (!coords) return;
      updatePin({ pinId: pin.pin_id, payload: coords });
    };

  const handleToggleStart = (pin: MapPin): void => {
    updatePin({
      pinId: pin.pin_id,
      payload: { is_start_location: !pin.is_start_location },
    });
  };

  if (!map) return null;

  if (!map.image_url) {
    return (
      <EmptyState
        title="Upload an image for this map first"
        description="Use the “Upload image” link next to the map's name above, then come back here to place pins."
      />
    );
  }

  return (
    <div className="space-y-2">
      {createError && <p className="text-xs text-red-400">{createError}</p>}
      <p className="text-xs text-zinc-500">
        Click anywhere on the map to place a Location entity's pin. Drag a pin
        to reposition it.
      </p>
      <div
        ref={canvasRef}
        onClick={handleCanvasClick}
        className="relative w-full select-none border border-zinc-800"
        style={{ aspectRatio: "16 / 9" }}
      >
        <img
          src={map.image_url}
          alt={map.name}
          className="pointer-events-none absolute inset-0 h-full w-full object-cover"
        />
        {pins.map((pin) => (
          <button
            key={pin.pin_id}
            onPointerDown={handlePinPointerDown(pin.pin_id)}
            onPointerMove={handlePinPointerMove(pin)}
            onPointerUp={handlePinPointerUp(pin)}
            title={entityName(pin.entity_id)}
            className={`absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1 whitespace-nowrap border px-2 py-1 text-xs ${
              pin.is_start_location
                ? "border-emerald-500 bg-emerald-950 text-emerald-300"
                : "border-zinc-400 bg-zinc-950 text-zinc-100"
            }`}
            style={{ left: `${pin.x * 100}%`, top: `${pin.y * 100}%` }}
          >
            {entityName(pin.entity_id)}
          </button>
        ))}
        {pendingPin && (
          <div
            className="absolute z-10 -translate-x-1/2 -translate-y-1/2 space-y-2 border border-zinc-400 bg-zinc-950 p-2"
            style={{
              left: `${pendingPin.x * 100}%`,
              top: `${pendingPin.y * 100}%`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <Select
              value={selectedEntityId}
              onChange={(e) => setSelectedEntityId(e.target.value)}
              options={[
                { value: "", label: "Choose a location…" },
                ...availableLocationEntities.map((e) => ({
                  value: e.entity_id,
                  label: e.canonical_name,
                })),
              ]}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handlePlacePin}
                disabled={!selectedEntityId}
              >
                Place
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setPendingPin(null)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
      <div className="space-y-1">
        {pins.map((pin) => (
          <div
            key={pin.pin_id}
            className="flex items-center justify-between border border-zinc-800 px-3 py-1.5 text-xs"
          >
            <span className="text-zinc-300">{entityName(pin.entity_id)}</span>
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleToggleStart(pin)}
                className={
                  pin.is_start_location
                    ? "text-emerald-400"
                    : "text-zinc-500 hover:text-zinc-300"
                }
              >
                {pin.is_start_location ? "★ Starting location" : "Set as start"}
              </button>
              <button
                onClick={() => deletePin(pin.pin_id)}
                className="text-zinc-500 hover:text-red-400"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
