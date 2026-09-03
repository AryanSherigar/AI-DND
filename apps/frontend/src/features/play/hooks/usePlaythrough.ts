import { useQuery } from "@tanstack/react-query";
import { getPlaythrough, PlaythroughResponse } from "../api/playthroughs.api";

export function usePlaythrough(playthroughId?: string) {
  return useQuery<PlaythroughResponse, Error>({
    queryKey: ["playthrough", playthroughId],
    queryFn: () => {
      if (!playthroughId) throw new Error("Playthrough ID is required");
      return getPlaythrough(playthroughId);
    },
    enabled: Boolean(playthroughId),
    staleTime: 0,
  });
}
