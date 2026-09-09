import { ScenarioMood } from "@/shared/types/audio.types";

export type MusicSource = "upload" | "generated" | "default";
export type MusicGenerationJobStatus =
  "pending" | "running" | "succeeded" | "failed";

export interface ScenarioMusicSlot {
  scenario_music_id: string;
  scenario_id: string;
  mood: ScenarioMood;
  source: MusicSource;
  track_url: string | null;
  generation_prompt: string | null;
  key: string | null;
  bpm: number | null;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface ScenarioMusicListResponse {
  items: ScenarioMusicSlot[];
}

export interface MusicGenerationRequest {
  mood: ScenarioMood;
  prompt: string;
}

export interface MusicGenerationJob {
  job_id: string;
  scenario_id: string;
  mood: ScenarioMood;
  status: MusicGenerationJobStatus;
  preview_url: string | null;
  key: string | null;
  bpm: number | null;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuotaStatus {
  scenario_generations_used: number;
  scenario_generations_limit: number;
  creator_generations_used_today: number;
  creator_generations_limit_per_day: number;
}
