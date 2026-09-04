import { apiClient } from "@/shared/lib/api-client";
import { MapConnection, MapPin, ScenarioMap } from "@/shared/types/map.types";

export interface MapListResponse {
  items: ScenarioMap[];
}

export interface MapCreate {
  name: string;
  display_order?: number;
}

export interface MapUpdate {
  name?: string;
  image_url?: string | null;
  display_order?: number;
}

export const listMaps = async (
  scenarioId: string,
): Promise<MapListResponse> => {
  const response = await apiClient.get<MapListResponse>(
    `/v1/scenarios/${scenarioId}/maps`,
  );
  return response.data;
};

export const createMap = async (
  scenarioId: string,
  payload: MapCreate,
): Promise<ScenarioMap> => {
  const response = await apiClient.post<ScenarioMap>(
    `/v1/scenarios/${scenarioId}/maps`,
    payload,
  );
  return response.data;
};

export const updateMap = async (
  scenarioId: string,
  mapId: string,
  payload: MapUpdate,
): Promise<ScenarioMap> => {
  const response = await apiClient.patch<ScenarioMap>(
    `/v1/scenarios/${scenarioId}/maps/${mapId}`,
    payload,
  );
  return response.data;
};

export const deleteMap = async (
  scenarioId: string,
  mapId: string,
): Promise<void> => {
  await apiClient.delete(`/v1/scenarios/${scenarioId}/maps/${mapId}`);
};

export interface MapPinListResponse {
  items: MapPin[];
}

export interface MapPinCreate {
  entity_id: string;
  x: number;
  y: number;
  is_start_location?: boolean;
}

export interface MapPinUpdate {
  x?: number;
  y?: number;
  is_start_location?: boolean;
}

export const listMapPins = async (
  scenarioId: string,
  mapId: string,
): Promise<MapPinListResponse> => {
  const response = await apiClient.get<MapPinListResponse>(
    `/v1/scenarios/${scenarioId}/maps/${mapId}/pins`,
  );
  return response.data;
};

export const createMapPin = async (
  scenarioId: string,
  mapId: string,
  payload: MapPinCreate,
): Promise<MapPin> => {
  const response = await apiClient.post<MapPin>(
    `/v1/scenarios/${scenarioId}/maps/${mapId}/pins`,
    payload,
  );
  return response.data;
};

export const updateMapPin = async (
  scenarioId: string,
  mapId: string,
  pinId: string,
  payload: MapPinUpdate,
): Promise<MapPin> => {
  const response = await apiClient.patch<MapPin>(
    `/v1/scenarios/${scenarioId}/maps/${mapId}/pins/${pinId}`,
    payload,
  );
  return response.data;
};

export const deleteMapPin = async (
  scenarioId: string,
  mapId: string,
  pinId: string,
): Promise<void> => {
  await apiClient.delete(
    `/v1/scenarios/${scenarioId}/maps/${mapId}/pins/${pinId}`,
  );
};

export interface MapConnectionListResponse {
  items: MapConnection[];
}

export interface MapConnectionCreate {
  entity_id_a: string;
  entity_id_b: string;
  label?: string | null;
}

export const listMapConnections = async (
  scenarioId: string,
): Promise<MapConnectionListResponse> => {
  const response = await apiClient.get<MapConnectionListResponse>(
    `/v1/scenarios/${scenarioId}/map-connections`,
  );
  return response.data;
};

export const createMapConnection = async (
  scenarioId: string,
  payload: MapConnectionCreate,
): Promise<MapConnection> => {
  const response = await apiClient.post<MapConnection>(
    `/v1/scenarios/${scenarioId}/map-connections`,
    payload,
  );
  return response.data;
};

export const deleteMapConnection = async (
  scenarioId: string,
  connectionId: string,
): Promise<void> => {
  await apiClient.delete(
    `/v1/scenarios/${scenarioId}/map-connections/${connectionId}`,
  );
};
