import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createFact,
  deleteFact,
  listFacts,
  updateFact,
} from "../api/facts.api";
import { FactCreate, FactListResponse, FactUpdate } from "../types/fact.types";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useFacts = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["facts", scenarioId] });

  const factsQuery = useQuery<FactListResponse, Error>({
    queryKey: ["facts", scenarioId],
    queryFn: () => listFacts(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: FactCreate) =>
      createFact(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      factId,
      payload,
    }: {
      factId: string;
      payload: FactUpdate;
    }) => updateFact(requireScenarioId(scenarioId), factId, payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (factId: string) =>
      deleteFact(requireScenarioId(scenarioId), factId),
    onSuccess: invalidate,
  });

  return {
    facts: factsQuery.data?.items ?? [],
    isLoading: factsQuery.isLoading,
    error: factsQuery.error,
    createFact: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(createMutation.error, "Failed to save fact.")
      : null,
    updateFact: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save fact.")
      : null,
    deleteFact: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error
      ? extractErrorMessage(deleteMutation.error, "Failed to save fact.")
      : null,
  };
};
