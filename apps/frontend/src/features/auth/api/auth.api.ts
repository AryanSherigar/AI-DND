import { apiClient } from "@/shared/lib/api-client";
import { TokenResponse } from "../types/auth.types";

export const exchangeFirebaseToken = async (
  firebaseIdToken: string,
): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>("/v1/auth/token", {
    firebase_id_token: firebaseIdToken,
  });
  return response.data;
};

// Refresh tokens rotate server-side on every use (the old jti is invalidated
// the instant a new one is issued), so two independent callers racing to
// refresh — AuthProvider's boot-time call and api-client's 401 interceptor
// both call this — send the same pre-rotation cookie and the loser gets
// rejected as "already used or rotated". Single-flighting collapses any
// concurrent callers within this tab onto one request/response instead of
// two, which is what the server-side rotation assumes.
let inFlightRefresh: Promise<TokenResponse> | null = null;

export const refreshAccessToken = async (): Promise<TokenResponse> => {
  if (inFlightRefresh) return inFlightRefresh;
  inFlightRefresh = apiClient
    .post<TokenResponse>("/v1/auth/refresh")
    .then((response) => response.data)
    .finally(() => {
      inFlightRefresh = null;
    });
  return inFlightRefresh;
};

export const logoutUser = async (): Promise<void> => {
  await apiClient.post("/v1/auth/logout");
};
