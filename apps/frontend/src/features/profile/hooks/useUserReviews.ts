import { useQuery } from "@tanstack/react-query";
import { fetchUserReviews } from "../api/profileApi";
import { UserReviewSummary } from "../types/profile.types";

export const useUserReviews = (userId: string, enabled = true) => {
  return useQuery<UserReviewSummary[], Error>({
    queryKey: ["user-reviews", userId],
    queryFn: () => fetchUserReviews(userId),
    enabled: Boolean(userId) && enabled,
    staleTime: 1000 * 60 * 5,
  });
};
