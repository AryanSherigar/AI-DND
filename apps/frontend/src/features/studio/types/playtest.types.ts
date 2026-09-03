export interface PlaythroughResponse {
  playthrough_id: string;
  scenario_id: string;
  scenario_title: string;
  created_by: string;
  state: Record<string, unknown>;
  checkpoint: string | null;
  turn_count: number;
  status: string;
  is_playtest: boolean;
  scenario_version: number;
  scenario_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  participant_id: string;
}
