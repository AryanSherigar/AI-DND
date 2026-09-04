import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  updateCharacterFields,
  PlaythroughResponse,
} from "../api/playthroughs.api";

export function useUpdateCharacterFields(playthroughId: string) {
  const queryClient = useQueryClient();

  return useMutation<PlaythroughResponse, Error, Record<string, unknown>>({
    mutationFn: (setupValues) =>
      updateCharacterFields(playthroughId, setupValues),
    onSuccess: (data) => {
      queryClient.setQueryData(["playthrough", playthroughId], data);
    },
  });
}
