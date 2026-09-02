import { useMutation, useQuery } from "@tanstack/react-query";
import { getScenario, publishScenario } from "../api/scenarios.api";

const extractErrorMessage = (err: unknown): string => {
  const anyErr = err as any;
  return (
    anyErr?.response?.data?.detail ||
    anyErr?.message ||
    "Failed to publish scenario."
  );
};

export const usePublish = (scenarioId: string | null) => {
  const publishMutation = useMutation({
    mutationFn: () => {
      if (!scenarioId) {
        throw new Error("Scenario must be saved before it can be published.");
      }
      return publishScenario(scenarioId);
    },
  });

  const statusQuery = useQuery({
    queryKey: ["scenario", scenarioId, "publish-status"],
    queryFn: () => getScenario(scenarioId as string),
    enabled: Boolean(scenarioId) && publishMutation.isSuccess,
    initialData: publishMutation.data,
    refetchInterval: (query) =>
      query.state.data?.status === "publishing" ? 1000 : false,
  });

  const scenario = statusQuery.data ?? publishMutation.data ?? null;
  const status = scenario?.status ?? null;

  return {
    scenario,
    status,
    isTriggering: publishMutation.isPending,
    isPolling: status === "publishing",
    triggerError: publishMutation.error
      ? extractErrorMessage(publishMutation.error)
      : null,
    publishError: scenario?.publish_error ?? null,
    publish: publishMutation.mutate,
  };
};
