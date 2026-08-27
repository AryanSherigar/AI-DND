import { apiClient } from '@/shared/lib/api-client';
import { TokenResponse } from '../types/auth.types';


export const exchangeFirebaseToken = async (firebaseIdToken: string): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/v1/auth/token', {
    firebase_id_token: firebaseIdToken
  });
  return response.data;
};

export const refreshAccessToken = async (): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/v1/auth/refresh');
  return response.data;
};
