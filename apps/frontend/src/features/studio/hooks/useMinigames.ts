import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createMinigame,
  deleteMinigame,
  listMinigames,
  reorderMinigames,
  updateMinigame,
} from "../api/minigames.api";
import {
  MinigameCreate,
  MinigameListResponse,
  MinigameUpdate,
} from "../types/minigame.types";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const requireScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) throw new Error("Scenario ID is required.");
  return scenarioId;
};

export const useMinigames = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const queryKey = ["minigames", scenarioId];
  const invalidate = () => queryClient.invalidateQueries({ queryKey });

  const minigamesQuery = useQuery<MinigameListResponse, Error>({
    queryKey,
    queryFn: () => listMinigames(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const createMutation = useMutation({
    mutationFn: (payload: MinigameCreate) =>
      createMinigame(requireScenarioId(scenarioId), payload),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      minigameId,
      payload,
    }: {
      minigameId: string;
      payload: MinigameUpdate;
    }) => updateMinigame(requireScenarioId(scenarioId), minigameId, payload),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (minigameId: string) =>
      deleteMinigame(requireScenarioId(scenarioId), minigameId),
    onSuccess: invalidate,
  });

  const reorderMutation = useMutation({
    mutationFn: (orderedMinigameIds: string[]) =>
      reorderMinigames(requireScenarioId(scenarioId), orderedMinigameIds),
    onMutate: async (orderedMinigameIds: string[]) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<MinigameListResponse>(queryKey);
      if (previous) {
        const byId = new Map(
          previous.items.map((item) => [item.minigame_id, item]),
        );
        const items = orderedMinigameIds
          .map((id, index) => {
            const item = byId.get(id);
            return item ? { ...item, priority: index } : null;
          })
          .filter(
            (item): item is MinigameListResponse["items"][number] =>
              item !== null,
          );
        queryClient.setQueryData<MinigameListResponse>(queryKey, { items });
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
    minigames: minigamesQuery.data?.items ?? [],
    isLoading: minigamesQuery.isLoading,
    error: minigamesQuery.error,
    createMinigame: createMutation.mutate,
    isCreating: createMutation.isPending,
    createError: createMutation.error
      ? extractErrorMessage(createMutation.error, "Failed to save minigame.")
      : null,
    updateMinigame: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save minigame.")
      : null,
    deleteMinigame: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error
      ? extractErrorMessage(deleteMutation.error, "Failed to save minigame.")
      : null,
    reorderMinigames: reorderMutation.mutate,
    isReordering: reorderMutation.isPending,
    reorderError: reorderMutation.error
      ? extractErrorMessage(reorderMutation.error, "Failed to save minigame.")
      : null,
  };
};
