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

export const GENRE_COLORS: Record<ScenarioGenre, string> = {
  "High Fantasy": "#D4AF6A",
  "Sci-Fi": "#4FD1E8",
  "Noir / Detective": "#C97A3D",
  Horror: "#8B2635",
  "Slice of Life": "#C98BA8",
  "Mystery/Thriller": "#5B6EE1",
  "Adventure/Survival": "#7FA65C",
  "Post-Apocalyptic/Dystopian": "#9B9B7A",
};

export interface ScenarioMock {
  id: string;
  title: string;
  logline: string;
  rating: number;
  playerCount: number;
  genre: ScenarioGenre;
  author: string;
  coverImageUrl: string;
  setupInputs?: SetupInputField[];
}
