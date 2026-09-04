import { apiClient } from "@/shared/lib/api-client";

export interface ToolCallLogEntry {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  is_valid: boolean;
}

export interface TurnLogResponse {
  turn_id: string;
  playthrough_id: string;
  turn_number: number;
  participant_id: string | null;
  action_text: string;
  narration_text: string | null;
  tool_calls: ToolCallLogEntry[];
  created_at: string;
}

export interface TurnLogListResponse {
  items: TurnLogResponse[];
  total_count: number;
}

export interface GetTurnsParams {
  share_token?: string;
  page?: number;
  page_size?: number;
  from_turn?: number;
}

export async function getTurns(
  playthroughId: string,
  params: GetTurnsParams = {},
): Promise<TurnLogListResponse> {
  const { data } = await apiClient.get<TurnLogListResponse>(
    `/v1/playthroughs/${playthroughId}/turns`,
    { params },
  );
  return data;
}
