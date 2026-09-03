import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createEndCondition,
  deleteEndCondition,
  listEndConditions,
  reorderEndConditions,
  updateEndCondition,
} from "../api/end_conditions.api";
import {
  EndConditionCreate,
  EndConditionListResponse,
  EndConditionUpdate,
} from "../types/end_condition.types";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useEndConditions = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const queryKey = ["end_conditions", scenarioId];
  const invalidate = () => queryClient.invalidateQueries({ queryKey });

  const endConditionsQuery = useQuery<EndConditionListResponse, Error>({
    queryKey,
    queryFn: () => listEndConditions(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: EndConditionCreate) =>
      createEndCondition(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      endConditionId,
      payload,
    }: {
      endConditionId: string;
      payload: EndConditionUpdate;
    }) =>
      updateEndCondition(requireScenarioId(scenarioId), endConditionId, payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (endConditionId: string) =>
      deleteEndCondition(requireScenarioId(scenarioId), endConditionId),
    onSuccess: invalidate,
  });

  const reorderMutation = useMutation({
    mutationFn: (orderedEndConditionIds: string[]) =>
      reorderEndConditions(requireScenarioId(scenarioId), orderedEndConditionIds),
    onMutate: async (orderedEndConditionIds: string[]) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<EndConditionListResponse>(queryKey);
      if (previous) {
        const byId = new Map(previous.items.map((item) => [item.end_condition_id, item]));
        const items = orderedEndConditionIds
          .map((id, index) => {
            const item = byId.get(id);
            return item ? { ...item, priority: index } : null;
          })
          .filter((item): item is EndConditionListResponse["items"][number] => item !== null);
        queryClient.setQueryData<EndConditionListResponse>(queryKey, { items });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: invalidate,
  });

  return {
    endConditions: endConditionsQuery.data?.items ?? [],
    isLoading: endConditionsQuery.isLoading,
    error: endConditionsQuery.error,
    createEndCondition: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(createMutation.error, "Failed to save end condition.")
      : null,
    updateEndCondition: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save end condition.")
      : null,
    deleteEndCondition: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error
      ? extractErrorMessage(deleteMutation.error, "Failed to save end condition.")
      : null,
    reorderEndConditions: reorderMutation.mutate,
    isReordering: reorderMutation.isPending,
    reorderError: reorderMutation.error
      ? extractErrorMessage(reorderMutation.error, "Failed to save end condition.")
      : null,
  };
};
