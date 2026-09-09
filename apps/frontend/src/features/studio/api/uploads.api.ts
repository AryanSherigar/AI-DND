import { apiClient } from "@/shared/lib/api-client";
import { IMAGE_GENERATION_TIMEOUT_MS } from "../constants/upload";

export interface ImageUploadResponse {
  url: string;
}

export const uploadCoverImage = async (
  file: File,
): Promise<ImageUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiClient.post<ImageUploadResponse>(
    "/v1/uploads/scenario-cover-image",
    formData,
    { headers: { "Content-Type": undefined } },
  );
  return response.data;
};

export interface CoverImageGenerationRequest {
  title: string;
  genre_tags: string[];
  opening_scene?: string;
}

export const generateCoverImage = async (
  body: CoverImageGenerationRequest,
): Promise<ImageUploadResponse> => {
  const response = await apiClient.post<ImageUploadResponse>(
    "/v1/uploads/generate-cover-image",
    body,
    { timeout: IMAGE_GENERATION_TIMEOUT_MS },
  );
  return response.data;
};

export const uploadMapImage = async (
  file: File,
): Promise<ImageUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiClient.post<ImageUploadResponse>(
    "/v1/uploads/scenario-map-image",
    formData,
    { headers: { "Content-Type": undefined } },
  );
  return response.data;
};

/** Upload creator-selected Dodge music through the same authenticated flow. */
export const uploadScenarioAudio = async (
  file: File,
): Promise<ImageUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiClient.post<ImageUploadResponse>(
    "/v1/uploads/scenario-audio",
    formData,
    { headers: { "Content-Type": undefined } },
  );
  return response.data;
};
