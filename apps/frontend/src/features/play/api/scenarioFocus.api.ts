import { apiClient } from "@/shared/lib/api-client";
import {
  PublicPlaythroughSummary,
  ScenarioDetailResponse,
  ScenarioReviewListResponse,
  ScenarioReviewResponse,
} from "../types/scenario";

export const fetchScenarioDetail = async (
  scenarioId: string,
): Promise<ScenarioDetailResponse> => {
  const response = await apiClient.get<ScenarioDetailResponse>(
    `/v1/scenarios/${scenarioId}`,
  );
  return response.data;
};

export const toggleBookmarkApi = async (
  scenarioId: string,
): Promise<{ is_bookmarked: boolean }> => {
  const response = await apiClient.post<{ is_bookmarked: boolean }>(
    `/v1/scenarios/${scenarioId}/bookmark`,
  );
  return response.data;
};

export const fetchScenarioReviews = async (
  scenarioId: string,
): Promise<ScenarioReviewListResponse> => {
  const response = await apiClient.get<ScenarioReviewListResponse>(
    `/v1/scenarios/${scenarioId}/reviews`,
  );
  return response.data;
};

export const submitScenarioReview = async (
  scenarioId: string,
  rating: number,
  comment?: string,
): Promise<ScenarioReviewResponse> => {
  const response = await apiClient.post<ScenarioReviewResponse>(
    `/v1/scenarios/${scenarioId}/reviews`,
    { rating, comment },
  );
  return response.data;
};

export const fetchPublicPlaythroughs = async (
  scenarioId: string,
): Promise<PublicPlaythroughSummary[]> => {
  const response = await apiClient.get<PublicPlaythroughSummary[]>(
    `/v1/scenarios/${scenarioId}/playthroughs`,
  );
  return response.data;
};
