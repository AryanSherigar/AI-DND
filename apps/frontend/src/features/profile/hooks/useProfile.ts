import { useQuery } from "@tanstack/react-query";
import { fetchMyProfile, fetchPublicProfile } from "../api/profileApi";
import { UserProfile } from "../types/profile.types";

export const useProfile = (userId?: string) => {
  const isMe = !userId || userId === "me";

  return useQuery<UserProfile, Error>({
    queryKey: ["user-profile", isMe ? "me" : userId],
    queryFn: () => (isMe ? fetchMyProfile() : fetchPublicProfile(userId!)),
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
};
