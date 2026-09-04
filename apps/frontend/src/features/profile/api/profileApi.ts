import { apiClient } from "@/shared/lib/api-client";
import {
  UserProfile,
  UserProfileUpdatePayload,
  UserPlaythroughSummary,
  UserReviewSummary,
} from "../types/profile.types";

export const fetchMyProfile = async (): Promise<UserProfile> => {
  const { data } = await apiClient.get<UserProfile>("/v1/users/me");
  return data;
};

export const fetchPublicProfile = async (
  userId: string,
): Promise<UserProfile> => {
  const { data } = await apiClient.get<UserProfile>(`/v1/users/${userId}`);
  return data;
};

export const updateProfile = async (
  payload: UserProfileUpdatePayload,
): Promise<UserProfile> => {
  const { data } = await apiClient.patch<UserProfile>("/v1/users/me", payload);
  return data;
};

export const fetchUserPlaythroughs = async (
  status?: string,
): Promise<UserPlaythroughSummary[]> => {
  const { data } = await apiClient.get<UserPlaythroughSummary[]>(
    "/v1/users/me/playthroughs",
    { params: status ? { status } : undefined },
  );
  return data;
};

export const fetchUserReviews = async (
  userId: string,
): Promise<UserReviewSummary[]> => {
  const { data } = await apiClient.get<UserReviewSummary[]>(
    `/v1/users/${userId}/reviews`,
  );
  return data;
};

export const abandonPlaythrough = async (
  playthroughId: string,
): Promise<void> => {
  await apiClient.post(`/v1/playthroughs/${playthroughId}/abandon`);
};

export const uploadAvatar = async (file: File): Promise<string> => {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<{ url: string }>(
    "/v1/uploads/avatar",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
    },
  );
  return data.url;
};

export const uploadBanner = async (file: File): Promise<string> => {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<{ url: string }>(
    "/v1/uploads/banner",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
    },
  );
  return data.url;
};
