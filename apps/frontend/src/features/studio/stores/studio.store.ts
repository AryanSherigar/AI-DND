import { create } from "zustand";

export interface StoryCard {
  id: string;
  type: string;
  name: string;
  content: string;
}

export interface NewbieDraft {
  title: string;
  genre_tags: string[];
  complexity_tier: "newbie" | "intermediate" | "master";
  player_count_support: "solo" | "multiplayer" | "both";
  estimated_playtime: string;
  cover_image_url: string;

  // Lore
  useSingleLorePrompt: boolean;
  worldLore: string;
  openingPrompt: string;
  mainConflict: string;
  includeConflict: boolean;
  storyCards: StoryCard[];
  singleLorePrompt: string;

  // Narrator
  aiInstructions: string;
  narrativeStyle: string;
}

const defaultDraft: NewbieDraft = {
  title: "",
  genre_tags: [],
  complexity_tier: "newbie",
  player_count_support: "solo",
  estimated_playtime: "",
  cover_image_url: "",
  useSingleLorePrompt: false,
  worldLore: "",
  openingPrompt: "",
  mainConflict: "",
  includeConflict: false,
  storyCards: [{ id: "1", type: "Character", name: "Hero", content: "" }],
  singleLorePrompt: "",
  aiInstructions: "",
  narrativeStyle: "",
};

interface StudioState {
  mode: "newbie" | "master";
  setMode: (mode: "newbie" | "master") => void;

  activeStep: number;
  setActiveStep: (step: number) => void;

  newbieDraft: NewbieDraft;
  updateNewbieDraft: (updates: Partial<NewbieDraft>) => void;

  lastSaved: Date | null;
  isSaving: boolean;
  setSaveState: (isSaving: boolean, lastSaved?: Date) => void;
}

export const useStudioStore = create<StudioState>((set) => ({
  mode: "newbie",
  setMode: (mode) => set({ mode }),

  activeStep: 1,
  setActiveStep: (step) => set({ activeStep: step }),

  newbieDraft: defaultDraft,
  updateNewbieDraft: (updates) =>
    set((state) => ({
      newbieDraft: { ...state.newbieDraft, ...updates },
    })),

  lastSaved: null,
  isSaving: false,
  setSaveState: (isSaving, lastSaved) =>
    set((state) => ({
      isSaving,
      lastSaved: lastSaved !== undefined ? lastSaved : state.lastSaved,
    })),
}));
