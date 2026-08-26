export interface UserResponse {
  user_id: string;
  display_name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserResponse;
}
