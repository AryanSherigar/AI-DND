import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MapCreate,
  MapListResponse,
  MapUpdate,
  createMap,
  deleteMap,
  listMaps,
  updateMap,
} from "../api/maps.api";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useMaps = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["maps", scenarioId] });

  const mapsQuery = useQuery<MapListResponse, Error>({
    queryKey: ["maps", scenarioId],
    queryFn: () => listMaps(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: MapCreate) =>
      createMap(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({ mapId, payload }: { mapId: string; payload: MapUpdate }) =>
      updateMap(requireScenarioId(scenarioId), mapId, payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (mapId: string) =>
      deleteMap(requireScenarioId(scenarioId), mapId),
    onSuccess: invalidate,
  });

  return {
    maps: mapsQuery.data?.items ?? [],
    isLoading: mapsQuery.isLoading,
    error: mapsQuery.error,
    createMap: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(createMutation.error, "Failed to save map.")
      : null,
    updateMap: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save map.")
      : null,
    deleteMap: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
  };
};
