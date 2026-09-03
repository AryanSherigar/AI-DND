import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createInvariant,
  deleteInvariant,
  listInvariants,
  updateInvariant,
} from "../api/invariants.api";
import {
  InvariantCreate,
  InvariantListResponse,
  InvariantUpdate,
} from "../types/invariant.types";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useInvariants = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["invariants", scenarioId] });

  const invariantsQuery = useQuery<InvariantListResponse, Error>({
    queryKey: ["invariants", scenarioId],
    queryFn: () => listInvariants(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: InvariantCreate) =>
      createInvariant(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      invariantId,
      payload,
    }: {
      invariantId: string;
      payload: InvariantUpdate;
    }) => updateInvariant(requireScenarioId(scenarioId), invariantId, payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (invariantId: string) =>
      deleteInvariant(requireScenarioId(scenarioId), invariantId),
    onSuccess: invalidate,
  });

  return {
    invariants: invariantsQuery.data?.items ?? [],
    isLoading: invariantsQuery.isLoading,
    error: invariantsQuery.error,
    createInvariant: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(createMutation.error, "Failed to save invariant.")
      : null,
    updateInvariant: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save invariant.")
      : null,
    deleteInvariant: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error
      ? extractErrorMessage(deleteMutation.error, "Failed to save invariant.")
      : null,
  };
};
