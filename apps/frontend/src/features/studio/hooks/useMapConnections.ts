import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MapConnectionCreate,
  MapConnectionListResponse,
  createMapConnection,
  deleteMapConnection,
  listMapConnections,
} from "../api/maps.api";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useMapConnections = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["map-connections", scenarioId],
    });

  const connectionsQuery = useQuery<MapConnectionListResponse, Error>({
    queryKey: ["map-connections", scenarioId],
    queryFn: () => listMapConnections(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: MapConnectionCreate) =>
      createMapConnection(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (connectionId: string) =>
      deleteMapConnection(requireScenarioId(scenarioId), connectionId),
    onSuccess: invalidate,
  });

  return {
    connections: connectionsQuery.data?.items ?? [],
    isLoading: connectionsQuery.isLoading,
    createConnection: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(
          createMutation.error,
          "Failed to create connection.",
        )
      : null,
    deleteConnection: deleteMutation.mutate,
  };
};
