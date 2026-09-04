import { useQuery } from "@tanstack/react-query";
import { fetchMyProfile, fetchPublicProfile } from "../api/profileApi";
import { UserProfile } from "../types/profile.types";

export interface UseProfileOptions {
  enabled?: boolean;
  currentUserId?: string;
}

export const useProfile = (userId?: string, options?: UseProfileOptions) => {
  const isMe = !userId || userId === "me";
  const profileKey = isMe ? (options?.currentUserId ?? "me") : userId;

  return useQuery<UserProfile, Error>({
    queryKey: ["user-profile", profileKey],
    queryFn: () => (isMe ? fetchMyProfile() : fetchPublicProfile(userId!)),
    staleTime: 1000 * 60 * 2, // 2 minutes
    enabled: options?.enabled ?? true,
  });
};
