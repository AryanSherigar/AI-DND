import { apiClient } from "@/shared/lib/api-client";
import {
  EntityTypeChangePreviewRequest,
  EntityTypeChangePreviewResponse,
} from "../types/entity.types";
import {
  ScenarioEntityTypeCreate,
  ScenarioEntityTypeListResponse,
  ScenarioEntityTypeResponse,
  ScenarioEntityTypeUpdate,
} from "../types/scenario_entity_type.types";

export const listScenarioEntityTypes = async (
  scenarioId: string,
): Promise<ScenarioEntityTypeListResponse> => {
  const response = await apiClient.get<ScenarioEntityTypeListResponse>(
    `/v1/scenarios/${scenarioId}/entity-types`,
  );
  return response.data;
};

export const createScenarioEntityType = async (
  scenarioId: string,
  payload: ScenarioEntityTypeCreate,
): Promise<ScenarioEntityTypeResponse> => {
  const response = await apiClient.post<ScenarioEntityTypeResponse>(
    `/v1/scenarios/${scenarioId}/entity-types`,
    payload,
  );
  return response.data;
};

export const updateScenarioEntityType = async (
  scenarioId: string,
  scenarioEntityTypeId: string,
  payload: ScenarioEntityTypeUpdate,
): Promise<ScenarioEntityTypeResponse> => {
  const response = await apiClient.patch<ScenarioEntityTypeResponse>(
    `/v1/scenarios/${scenarioId}/entity-types/${scenarioEntityTypeId}`,
    payload,
  );
  return response.data;
};

export const deleteScenarioEntityType = async (
  scenarioId: string,
  scenarioEntityTypeId: string,
): Promise<void> => {
  await apiClient.delete(
    `/v1/scenarios/${scenarioId}/entity-types/${scenarioEntityTypeId}`,
  );
};

export const previewEntityTypeChange = async (
  scenarioId: string,
  entityId: string,
  payload: EntityTypeChangePreviewRequest,
): Promise<EntityTypeChangePreviewResponse> => {
  const response = await apiClient.post<EntityTypeChangePreviewResponse>(
    `/v1/scenarios/${scenarioId}/entities/${entityId}/type-change-preview`,
    payload,
  );
  return response.data;
};
