import { apiClient } from "@/shared/lib/api-client";
import { PlaythroughResponse } from "./playthroughs.api";

export type ShareMode = "spectate" | "join";

export interface ShareResponse {
  share_id: string;
  share_token: string;
  mode: ShareMode;
  playthrough_id: string;
  url: string;
  created_at: string;
}

export async function createShare(
  playthroughId: string,
  mode: ShareMode,
): Promise<ShareResponse> {
  const { data } = await apiClient.post<ShareResponse>(
    `/v1/playthroughs/${playthroughId}/share`,
    { mode },
  );
  return data;
}

export async function joinPlaythrough(
  shareToken: string,
): Promise<PlaythroughResponse> {
  const { data } = await apiClient.post<PlaythroughResponse>(
    "/v1/playthroughs/join",
    { share_token: shareToken },
  );
  return data;
}
