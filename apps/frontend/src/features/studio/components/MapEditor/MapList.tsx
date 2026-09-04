import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Input } from "@/shared/components/ui/Input";
import { useMaps } from "../../hooks/useMaps";
import { useUploadMapImage } from "../../hooks/useUploadMapImage";
import {
  MAX_COVER_IMAGE_BYTES,
  ALLOWED_COVER_IMAGE_TYPES,
} from "../../constants/upload";
import { MapListProps } from "./MapEditor.types";

export const MapList: React.FC<MapListProps> = ({
  scenarioId,
  selectedMapId,
  onSelectMap,
}) => {
  const { maps, isLoading, createMap, updateMap, deleteMap, createError } =
    useMaps(scenarioId);
  const uploadMapImage = useUploadMapImage();
  const [newMapName, setNewMapName] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleCreate = (): void => {
    if (!newMapName.trim()) return;
    createMap(
      { name: newMapName.trim(), display_order: maps.length },
      { onSuccess: (created) => onSelectMap(created.map_id) },
    );
    setNewMapName("");
  };

  const handleImageChange =
    (mapId: string) =>
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) return;
      setUploadError(null);
      if (!ALLOWED_COVER_IMAGE_TYPES.includes(file.type)) {
        setUploadError("Unsupported image format. Use JPEG, PNG, or WebP.");
        return;
      }
      if (file.size > MAX_COVER_IMAGE_BYTES) {
        setUploadError("Image exceeds the 5MB size limit.");
        return;
      }
      uploadMapImage.mutate(file, {
        onSuccess: (result) =>
          updateMap({ mapId, payload: { image_url: result.url } }),
        onError: () => setUploadError("Failed to upload map image."),
      });
    };

  const handleDelete = (mapId: string): void => {
    deleteMap(mapId);
    if (selectedMapId === mapId) onSelectMap("");
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Input
          value={newMapName}
          onChange={(e) => setNewMapName(e.target.value)}
          placeholder="New map name (e.g. World Map)"
        />
        <Button size="sm" onClick={handleCreate} disabled={!newMapName.trim()}>
          Add Map
        </Button>
      </div>
      {createError && <p className="text-xs text-red-400">{createError}</p>}
      {uploadError && <p className="text-xs text-red-400">{uploadError}</p>}
      {isLoading && <p className="text-sm text-zinc-500">Loading maps…</p>}
      {!isLoading && maps.length === 0 && (
        <EmptyState
          title="No maps yet"
          description="Add a map, upload an image for it, then pin your Location entities onto it."
        />
      )}
      <div className="space-y-2">
        {maps.map((map) => (
          <div
            key={map.map_id}
            className={`flex items-center justify-between border px-3 py-2 ${
              selectedMapId === map.map_id
                ? "border-zinc-400 bg-zinc-900"
                : "border-zinc-800"
            }`}
          >
            <button
              onClick={() => onSelectMap(map.map_id)}
              className="flex-1 text-left text-sm text-zinc-200"
            >
              {map.name}
              {!map.image_url && (
                <span className="ml-2 text-xs text-zinc-600">
                  (no image uploaded)
                </span>
              )}
            </button>
            <label className="cursor-pointer px-2 py-1 text-xs text-zinc-400 hover:text-zinc-100">
              Upload image
              <input
                type="file"
                accept={ALLOWED_COVER_IMAGE_TYPES.join(",")}
                className="hidden"
                onChange={handleImageChange(map.map_id)}
              />
            </label>
            <Button
              size="sm"
              variant="danger"
              onClick={() => handleDelete(map.map_id)}
            >
              Delete
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
};
