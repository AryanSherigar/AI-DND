import { SetupInputField } from "@/features/studio/stores/studio.store";

export type ScenarioGenre =
  | "High Fantasy"
  | "Sci-Fi"
  | "Noir / Detective"
  | "Horror"
  | "Slice of Life"
  | "Mystery/Thriller"
  | "Adventure/Survival"
  | "Post-Apocalyptic/Dystopian";

export const GENRE_COLORS: Record<string, string> = {
  "High Fantasy": "#D4AF6A",
  "Sci-Fi": "#4FD1E8",
  "Noir / Detective": "#C97A3D",
  Horror: "#8B2635",
  "Slice of Life": "#C98BA8",
  "Mystery/Thriller": "#5B6EE1",
  "Adventure/Survival": "#7FA65C",
  "Post-Apocalyptic/Dystopian": "#9B9B7A",
  fantasy: "#D4AF6A",
  "dungeon-crawl": "#8B2635",
  sci_fi: "#4FD1E8",
};

export interface ScenarioMock {
  id: string;
  title: string;
  logline: string;
  rating: number;
  playerCount: number;
  genre: string;
  author: string;
  coverImageUrl: string;
  setupInputs?: SetupInputField[];
}

export interface ScenarioSummaryResponse {
  scenario_id: string;
  creator_id: string;
  title: string;
  logline: string | null;
  mode: "newbie" | "master";
  status: "draft" | "publishing" | "published" | "publish_failed" | "archived";
  genre_tags: string[];
  complexity_tier: "newbie" | "intermediate" | "master";
  player_count_support: "solo" | "multiplayer" | "both";
  estimated_playtime: string | null;
  cover_image_url: string | null;
  content_tag: string | null;
  play_count: number;
  rating_avg: string;
  created_at: string;
  updated_at: string;
}

export interface ScenarioListResponse {
  items: ScenarioSummaryResponse[];
  next_cursor: string | null;
  total_count: number;
}

export interface GetScenariosParams {
  creator_id?: string;
  mine?: boolean;
  saved?: boolean;
  played?: boolean;
  genre_tags?: string[];
  complexity_tier?: "newbie" | "master" | "intermediate";
  player_count_support?: "solo" | "multiplayer" | "both";
  sort?: "created_at" | "play_count" | "rating_avg";
  limit?: number;
  offset?: number;
}

export interface ScenarioDetailResponse extends ScenarioSummaryResponse {
  creator_display_name?: string | null;
  is_bookmarked?: boolean;
  can_review?: boolean;
  world_data?: Record<string, unknown>;
  setup_schema?: SetupInputField[];
  narrator_persona?: string | null;
  rules?: Record<string, unknown>;
}

export interface ScenarioReviewResponse {
  review_id: string;
  scenario_id: string;
  user_id: string;
  user_display_name: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface ScenarioReviewListResponse {
  items: ScenarioReviewResponse[];
  total_count: number;
  average_rating: number;
}

export interface PublicPlaythroughSummary {
  playthrough_id: string;
  player_name: string;
  character_name: string | null;
  turn_count: number;
  status: string;
  updated_at: string;
}
