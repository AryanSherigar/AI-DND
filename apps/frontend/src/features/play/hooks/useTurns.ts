import { useQuery } from "@tanstack/react-query";
import { getTurns, GetTurnsParams, TurnLogListResponse } from "../api/turns.api";

export function usePlaythroughTurns(
  playthroughId?: string,
  params: GetTurnsParams = {},
) {
  return useQuery<TurnLogListResponse, Error>({
    queryKey: ["playthrough-turns", playthroughId, params],
    queryFn: () => {
      if (!playthroughId) throw new Error("Playthrough ID is required");
      return getTurns(playthroughId, params);
    },
    enabled: Boolean(playthroughId),
    staleTime: 0,
  });
}
