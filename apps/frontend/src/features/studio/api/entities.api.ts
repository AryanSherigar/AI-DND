import { apiClient } from "@/shared/lib/api-client";
import {
  EntityCreate,
  EntityListResponse,
  EntityResponse,
  EntityUpdate,
} from "../types/entity.types";

export const listEntities = async (
  scenarioId: string,
): Promise<EntityListResponse> => {
  const response = await apiClient.get<EntityListResponse>(
    `/v1/scenarios/${scenarioId}/entities`,
  );
  return response.data;
};

export const getEntity = async (
  scenarioId: string,
  entityId: string,
): Promise<EntityResponse> => {
  const response = await apiClient.get<EntityResponse>(
    `/v1/scenarios/${scenarioId}/entities/${entityId}`,
  );
  return response.data;
};

export const createEntity = async (
  scenarioId: string,
  payload: EntityCreate,
): Promise<EntityResponse> => {
  const response = await apiClient.post<EntityResponse>(
    `/v1/scenarios/${scenarioId}/entities`,
    payload,
  );
  return response.data;
};

export const updateEntity = async (
  scenarioId: string,
  entityId: string,
  payload: EntityUpdate,
): Promise<EntityResponse> => {
  const response = await apiClient.patch<EntityResponse>(
    `/v1/scenarios/${scenarioId}/entities/${entityId}`,
    payload,
  );
  return response.data;
};

export const deleteEntity = async (
  scenarioId: string,
  entityId: string,
): Promise<void> => {
  await apiClient.delete(`/v1/scenarios/${scenarioId}/entities/${entityId}`);
};
