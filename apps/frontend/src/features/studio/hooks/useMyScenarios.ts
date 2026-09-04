import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteScenario, listScenarios } from "../api/scenarios.api";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const MY_SCENARIOS_QUERY_KEY = ["scenarios", "mine"];

export const useMyScenarios = () => {
  const queryClient = useQueryClient();

  const scenariosQuery = useQuery({
    queryKey: MY_SCENARIOS_QUERY_KEY,
    queryFn: () => listScenarios({ mine: true, sort: "created_at" }),
  });

  const deleteMutation = useMutation({
    mutationFn: (scenarioId: string) => deleteScenario(scenarioId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MY_SCENARIOS_QUERY_KEY });
    },
  });

  return {
    scenarios: scenariosQuery.data?.items ?? [],
    totalCount: scenariosQuery.data?.total_count ?? 0,
    isLoading: scenariosQuery.isLoading,
    error: scenariosQuery.error,
    deleteScenario: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error
      ? extractErrorMessage(deleteMutation.error, "Failed to delete scenario.")
      : null,
  };
};
