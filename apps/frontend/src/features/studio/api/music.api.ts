import { apiClient } from "@/shared/lib/api-client";
import { ScenarioMood } from "@/shared/types/audio.types";
import {
  MusicGenerationJob,
  MusicGenerationRequest,
  QuotaStatus,
  ScenarioMusicListResponse,
  ScenarioMusicSlot,
} from "../types/music.types";

export const listScenarioMusic = async (
  scenarioId: string,
): Promise<ScenarioMusicListResponse> => {
  const response = await apiClient.get<ScenarioMusicListResponse>(
    `/v1/scenarios/${scenarioId}/music`,
  );
  return response.data;
};

export const uploadMusicTrack = async (
  scenarioId: string,
  mood: ScenarioMood,
  file: File,
): Promise<ScenarioMusicSlot> => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiClient.post<ScenarioMusicSlot>(
    `/v1/scenarios/${scenarioId}/music/${mood}/upload`,
    formData,
    { headers: { "Content-Type": undefined } },
  );
  return response.data;
};

export const setDefaultMusicTrack = async (
  scenarioId: string,
  mood: ScenarioMood,
): Promise<ScenarioMusicSlot> => {
  const response = await apiClient.post<ScenarioMusicSlot>(
    `/v1/scenarios/${scenarioId}/music/${mood}/default`,
  );
  return response.data;
};

export const requestMusicGeneration = async (
  scenarioId: string,
  payload: MusicGenerationRequest,
): Promise<MusicGenerationJob> => {
  const response = await apiClient.post<MusicGenerationJob>(
    `/v1/scenarios/${scenarioId}/music/generate`,
    payload,
  );
  return response.data;
};

export const getMusicGenerationJob = async (
  scenarioId: string,
  jobId: string,
): Promise<MusicGenerationJob> => {
  const response = await apiClient.get<MusicGenerationJob>(
    `/v1/scenarios/${scenarioId}/music/jobs/${jobId}`,
  );
  return response.data;
};

export const confirmGeneratedTrack = async (
  scenarioId: string,
  jobId: string,
): Promise<ScenarioMusicSlot> => {
  const response = await apiClient.post<ScenarioMusicSlot>(
    `/v1/scenarios/${scenarioId}/music/jobs/${jobId}/confirm`,
  );
  return response.data;
};

export const discardMusicGenerationJob = async (
  scenarioId: string,
  jobId: string,
): Promise<void> => {
  await apiClient.delete(`/v1/scenarios/${scenarioId}/music/jobs/${jobId}`);
};

export const getMusicQuota = async (
  scenarioId: string,
): Promise<QuotaStatus> => {
  const response = await apiClient.get<QuotaStatus>(
    `/v1/scenarios/${scenarioId}/music/quota`,
  );
  return response.data;
};
