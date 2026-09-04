import { apiClient } from "@/shared/lib/api-client";

export interface CreatePlaythroughPayload {
  scenario_id: string;
  setup_values: Record<string, unknown>;
}

export interface ParticipantSummary {
  participant_id: string;
  user_id: string;
  role: "owner" | "joined";
  turn_order_position: number;
}

export interface PlaythroughResponse {
  playthrough_id: string;
  scenario_id: string;
  scenario_title: string;
  created_by: string;
  state: Record<string, unknown>;
  checkpoint: string | null;
  turn_count: number;
  status: string;
  scenario_version: number;
  scenario_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  // The requesting user's own participant_id — required by POST /v1/turn.
  participant_id: string;
  participants: ParticipantSummary[];
  // Master-mode-only; [] for newbie or no scenario_conditions currently true.
  active_conditions: string[];
}

export async function createPlaythrough(
  payload: CreatePlaythroughPayload,
): Promise<PlaythroughResponse> {
  const response = await apiClient.post<PlaythroughResponse>(
    "/v1/playthroughs",
    payload,
  );
  return response.data;
}

export async function getPlaythrough(
  playthroughId: string,
): Promise<PlaythroughResponse> {
  const response = await apiClient.get<PlaythroughResponse>(
    `/v1/playthroughs/${playthroughId}`,
  );
  return response.data;
}

export async function updateCharacterFields(
  playthroughId: string,
  setupValues: Record<string, unknown>,
): Promise<PlaythroughResponse> {
  const response = await apiClient.patch<PlaythroughResponse>(
    `/v1/playthroughs/${playthroughId}/character`,
    { setup_values: setupValues },
  );
  return response.data;
}
