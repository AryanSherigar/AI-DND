import { apiClient } from "@/shared/lib/api-client";
import { SetupInputField } from "../stores/studio.store";

export type ScenarioStatus =
  "draft" | "publishing" | "published" | "publish_failed" | "archived";

export interface CreateScenarioPayload {
  title: string;
  logline?: string;
  mode: "newbie" | "master";
  complexity_tier: "newbie" | "intermediate" | "master";
  player_count_support?: "solo" | "multiplayer" | "both";
  genre_tags?: string[];
  estimated_playtime?: string;
  cover_image_url?: string;
  content_tag?: string;
  narrator_persona?: string;
  world_data?: Record<string, unknown>;
  setup_schema?: SetupInputField[];
}

export interface ScenarioResponse {
  scenario_id: string;
  creator_id: string;
  title: string;
  logline: string | null;
  mode: string;
  status: ScenarioStatus;
  genre_tags: string[];
  complexity_tier: string;
  player_count_support: string;
  estimated_playtime: string | null;
  cover_image_url: string | null;
  content_tag: string | null;
  publish_error: string | null;
  published_at: string | null;
  world_data: Record<string, unknown>;
  setup_schema: SetupInputField[];
  created_at: string;
  updated_at: string;
}

export const createScenario = async (
  payload: CreateScenarioPayload,
): Promise<ScenarioResponse> => {
  const response = await apiClient.post<ScenarioResponse>(
    "/v1/scenarios",
    payload,
  );
  return response.data;
};

export const getScenario = async (
  scenarioId: string,
): Promise<ScenarioResponse> => {
  const response = await apiClient.get<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}`,
  );
  return response.data;
};

export const updateScenarioContentTag = async (
  scenarioId: string,
  content_tag: string,
): Promise<ScenarioResponse> => {
  const response = await apiClient.patch<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}`,
    { content_tag },
  );
  return response.data;
};

export const publishScenario = async (
  scenarioId: string,
): Promise<ScenarioResponse> => {
  const response = await apiClient.post<ScenarioResponse>(
    `/v1/scenarios/${scenarioId}/publish`,
  );
  return response.data;
};
