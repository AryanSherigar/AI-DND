import { useMutation } from "@tanstack/react-query";
import { previewEntityTypeChange } from "../api/scenario_entity_types.api";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

export const useEntityTypeChangePreview = (scenarioId: string) => {
  const previewMutation = useMutation({
    mutationFn: ({
      entityId,
      newEntityType,
    }: {
      entityId: string;
      newEntityType: string;
    }) =>
      previewEntityTypeChange(scenarioId, entityId, {
        new_entity_type: newEntityType,
      }),
  });

  return {
    previewTypeChange: previewMutation.mutateAsync,
    isPreviewing: previewMutation.isPending,
    previewError: previewMutation.error
      ? extractErrorMessage(
          previewMutation.error,
          "Failed to preview type change.",
        )
      : null,
  };
};
