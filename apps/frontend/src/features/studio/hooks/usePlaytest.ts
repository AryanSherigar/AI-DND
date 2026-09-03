import { useMutation } from "@tanstack/react-query";
import { playtestScenario } from "../api/playtest.api";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

export const usePlaytest = (scenarioId: string) => {
  const playtestMutation = useMutation({
    mutationFn: () => playtestScenario(scenarioId),
  });

  return {
    playtest: playtestMutation.mutate,
    playthrough: playtestMutation.data ?? null,
    isPlaytesting: playtestMutation.isPending,
    playtestError: playtestMutation.error
      ? extractErrorMessage(playtestMutation.error, "Failed to start playtest.")
      : null,
  };
};
