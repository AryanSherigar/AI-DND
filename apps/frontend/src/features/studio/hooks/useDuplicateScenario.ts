import { useMutation } from "@tanstack/react-query";
import { duplicateScenario } from "../api/duplicate.api";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

export const useDuplicateScenario = (scenarioId: string) => {
  const duplicateMutation = useMutation({
    mutationFn: () => duplicateScenario(scenarioId),
  });

  return {
    duplicate: duplicateMutation.mutate,
    duplicatedScenario: duplicateMutation.data ?? null,
    isDuplicating: duplicateMutation.isPending,
    duplicateError: duplicateMutation.error
      ? extractErrorMessage(
          duplicateMutation.error,
          "Failed to duplicate scenario.",
        )
      : null,
  };
};
