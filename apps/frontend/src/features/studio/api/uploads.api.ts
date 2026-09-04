import { apiClient } from "@/shared/lib/api-client";

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
