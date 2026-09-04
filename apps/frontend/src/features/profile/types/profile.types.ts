export interface UserStats {
  campaigns_played_count: number;
  victories_count: number;
  total_turns_taken: number;
  scenarios_authored_count: number;
  total_plays_received: number;
}

export interface UserProfile {
  user_id: string;
  display_name: string;
  bio: string | null;
  avatar_url: string | null;
  banner_url: string | null;
  created_at: string;
  auth_provider_id?: string;
  stats: UserStats;
}

export interface UserProfileUpdatePayload {
  display_name?: string;
  bio?: string | null;
  avatar_url?: string | null;
  banner_url?: string | null;
}

export interface UserPlaythroughSummary {
  playthrough_id: string;
  scenario_id: string;
  scenario_title: string;
  scenario_mode: "newbie" | "master";
  cover_image_url: string | null;
  turn_count: number;
  status: "active" | "completed" | "abandoned";
  ended_outcome_tag: "win" | "lose" | null;
  ended_outcome_title: string | null;
  ended_outcome_text: string | null;
  character_name: string | null;
  character_archetype: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserReviewSummary {
  review_id: string;
  scenario_id: string;
  scenario_title: string;
  rating: number;
  review_text: string | null;
  created_at: string;
}
