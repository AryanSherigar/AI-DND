import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getScenario, updateScenario } from "../api/scenarios.api";
import { ScenarioResponse, ScenarioUpdate } from "../types/scenario.types";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";
import { useStudioStore } from "../stores/studio.store";

export const useScenario = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const queryKey = ["scenario", scenarioId];
  const setSaveState = useStudioStore((s) => s.setSaveState);

  const scenarioQuery = useQuery<ScenarioResponse, Error>({
    queryKey,
    queryFn: () => getScenario(scenarioId as string),
    enabled: Boolean(scenarioId),
  });

  const updateMutation = useMutation({
    mutationFn: (payload: ScenarioUpdate) => {
      if (!scenarioId) throw new Error("Scenario ID is required.");
      setSaveState(true);
      return updateScenario(scenarioId, payload);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, updated);
      setSaveState(false, new Date());
    },
    onError: () => {
      setSaveState(false);
    },
  });

  return {
    scenario: scenarioQuery.data ?? null,
    isLoading: scenarioQuery.isLoading,
    error: scenarioQuery.error,
    updateScenario: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error
      ? extractErrorMessage(updateMutation.error, "Failed to save scenario.")
      : null,
  };
};
