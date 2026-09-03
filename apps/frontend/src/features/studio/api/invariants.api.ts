import { apiClient } from "@/shared/lib/api-client";
import {
  InvariantCreate,
  InvariantListResponse,
  InvariantResponse,
  InvariantUpdate,
} from "../types/invariant.types";

export const listInvariants = async (
  scenarioId: string,
): Promise<InvariantListResponse> => {
  const response = await apiClient.get<InvariantListResponse>(
    `/v1/scenarios/${scenarioId}/invariants`,
  );
  return response.data;
};

export const getInvariant = async (
  scenarioId: string,
  invariantId: string,
): Promise<InvariantResponse> => {
  const response = await apiClient.get<InvariantResponse>(
    `/v1/scenarios/${scenarioId}/invariants/${invariantId}`,
  );
  return response.data;
};

export const createInvariant = async (
  scenarioId: string,
  payload: InvariantCreate,
): Promise<InvariantResponse> => {
  const response = await apiClient.post<InvariantResponse>(
    `/v1/scenarios/${scenarioId}/invariants`,
    payload,
  );
  return response.data;
};

export const updateInvariant = async (
  scenarioId: string,
  invariantId: string,
  payload: InvariantUpdate,
): Promise<InvariantResponse> => {
  const response = await apiClient.patch<InvariantResponse>(
    `/v1/scenarios/${scenarioId}/invariants/${invariantId}`,
    payload,
  );
  return response.data;
};

export const deleteInvariant = async (
  scenarioId: string,
  invariantId: string,
): Promise<void> => {
  await apiClient.delete(
    `/v1/scenarios/${scenarioId}/invariants/${invariantId}`,
  );
};
