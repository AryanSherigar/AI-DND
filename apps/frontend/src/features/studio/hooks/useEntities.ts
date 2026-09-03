import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createEntity,
  deleteEntity,
  listEntities,
  updateEntity,
} from "../api/entities.api";
import {
  EntityCreate,
  EntityListResponse,
  EntityUpdate,
} from "../types/entity.types";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useEntities = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["entities", scenarioId] });

  const entitiesQuery = useQuery<EntityListResponse, Error>({
    queryKey: ["entities", scenarioId],
    queryFn: () => listEntities(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: EntityCreate) =>
      createEntity(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      entityId,
      payload,
    }: {
      entityId: string;
      payload: EntityUpdate;
    }) => updateEntity(requireScenarioId(scenarioId), entityId, payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (entityId: string) =>
      deleteEntity(requireScenarioId(scenarioId), entityId),
    onSuccess: invalidate,
  });

  return {
    entities: entitiesQuery.data?.items ?? [],
    isLoading: entitiesQuery.isLoading,
    error: entitiesQuery.error,
    createEntity: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(createMutation.error, "Failed to save entity.")
      : null,
    updateEntity: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save entity.")
      : null,
    deleteEntity: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error
      ? extractErrorMessage(deleteMutation.error, "Failed to save entity.")
      : null,
  };
};
