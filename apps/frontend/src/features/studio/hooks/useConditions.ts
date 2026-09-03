import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCondition,
  deleteCondition,
  listConditions,
  updateCondition,
} from "../api/conditions.api";
import {
  ConditionCreate,
  ConditionListResponse,
  ConditionUpdate,
} from "../types/condition.types";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useConditions = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["conditions", scenarioId] });

  const conditionsQuery = useQuery<ConditionListResponse, Error>({
    queryKey: ["conditions", scenarioId],
    queryFn: () => listConditions(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: ConditionCreate) =>
      createCondition(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      conditionId,
      payload,
    }: {
      conditionId: string;
      payload: ConditionUpdate;
    }) => updateCondition(requireScenarioId(scenarioId), conditionId, payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (conditionId: string) =>
      deleteCondition(requireScenarioId(scenarioId), conditionId),
    onSuccess: invalidate,
  });

  return {
    conditions: conditionsQuery.data?.items ?? [],
    isLoading: conditionsQuery.isLoading,
    error: conditionsQuery.error,
    createCondition: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(createMutation.error, "Failed to save condition.")
      : null,
    updateCondition: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save condition.")
      : null,
    deleteCondition: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error
      ? extractErrorMessage(deleteMutation.error, "Failed to save condition.")
      : null,
  };
};
