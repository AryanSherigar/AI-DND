import { useQuery } from "@tanstack/react-query";
import { fetchUserPlaythroughs } from "../api/profileApi";
import { UserPlaythroughSummary } from "../types/profile.types";

export const useUserPlaythroughs = (status?: string, enabled = true) => {
  return useQuery<UserPlaythroughSummary[], Error>({
    queryKey: ["user-playthroughs", status ?? "all"],
    queryFn: () => fetchUserPlaythroughs(status),
    enabled,
    staleTime: 0, // Keep active playthroughs fresh
  });
};
