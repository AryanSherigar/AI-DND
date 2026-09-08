import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getScenario, publishScenario } from "../api/scenarios.api";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

const assertScenarioId = (scenarioId: string | null): string => {
  if (!scenarioId) {
    throw new Error("Scenario must be saved before it can be published.");
  }
  return scenarioId;
};

const resolvePublishInterval = (
  query: { state: { data?: { status?: string } } },
  onComplete: () => void,
): number | false => {
  const isPublishing = query.state.data?.status === "publishing";
  if (!isPublishing && query.state.data?.status === "published") {
    onComplete();
  }
  return isPublishing ? 1000 : false;
};

export const usePublish = (scenarioId: string | null) => {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["my-scenarios"] });
    if (scenarioId) {
      queryClient.invalidateQueries({ queryKey: ["scenario", scenarioId] });
    }
  };

  const publishMutation = useMutation({
    mutationFn: () => publishScenario(assertScenarioId(scenarioId)),
    onSuccess: invalidate,
  });

  const statusQuery = useQuery({
    queryKey: ["scenario", scenarioId, "publish-status"],
    queryFn: () => getScenario(scenarioId as string),
    enabled: Boolean(scenarioId) && publishMutation.isSuccess,
    initialData: publishMutation.data,
    refetchInterval: (query) => resolvePublishInterval(query, invalidate),
  });

  const scenario = statusQuery.data ?? publishMutation.data ?? null;
  const status = scenario?.status ?? null;

  return {
    scenario,
    status,
    isTriggering: publishMutation.isPending,
    isPolling: status === "publishing",
    triggerError: publishMutation.error
      ? extractErrorMessage(
          publishMutation.error,
          "Failed to publish scenario.",
        )
      : null,
    publishError: scenario?.publish_error ?? null,
    publish: publishMutation.mutate,
  };
};
