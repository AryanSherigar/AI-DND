import { create } from "zustand";
import { MasterModeTabId } from "../components/Layout/MasterModeStudioLayout.types";

export type SetupInputType =
  "single_select" | "multi_select" | "text" | "textarea" | "number";

export interface SetupInputOption {
  id: string;
  label: string;
  value: string;
}

export interface SetupInputField {
  id: string;
  key: string;
  label: string;
  type: SetupInputType;
  description?: string;
  placeholder?: string;
  required: boolean;
  options: SetupInputOption[];
  defaultValue?: string | string[] | number;
  is_character_name?: boolean;
  predicate?: string;
}

export interface StoryCard {
  id: string;
  type: string;
  name: string;
  content: string;
}

export interface NewbieDraft {
  title: string;
  logline: string;
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

  // Player Setup
  setupInputs: SetupInputField[];

  // Narrator
  aiInstructions: string;
  narrativeStyle: string;
}

const defaultDraft: NewbieDraft = {
  title: "",
  logline: "",
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
  setupInputs: [
    {
      id: "1",
      key: "character_class",
      label: "Character Role / Class",
      type: "single_select",
      description: "Choose your primary discipline in this world",
      required: true,
      options: [
        { id: "opt-1", label: "Solar Sentinel", value: "solar_sentinel" },
        { id: "opt-2", label: "Aether Scholar", value: "aether_scholar" },
        { id: "opt-3", label: "Shadow Rogue", value: "shadow_rogue" },
      ],
      defaultValue: "solar_sentinel",
    },
  ],
  aiInstructions: "",
  narrativeStyle: "",
};

export interface ScenarioDraftHydration {
  title?: string;
  logline?: string | null;
  genre_tags?: string[];
  complexity_tier?: "newbie" | "intermediate" | "master";
  player_count_support?: "solo" | "multiplayer" | "both";
  estimated_playtime?: string | null;
  cover_image_url?: string | null;
  narrator_persona?: string | null;
  world_data?: Record<string, unknown>;
  setup_schema?: SetupInputField[];
}

interface StudioState {
  mode: "newbie" | "master";
  setMode: (mode: "newbie" | "master") => void;

  activeStep: number;
  setActiveStep: (step: number) => void;

  newbieDraft: NewbieDraft;
  updateNewbieDraft: (updates: Partial<NewbieDraft>) => void;
  hydrateFromScenario: (scenario: ScenarioDraftHydration) => void;
  resetDraft: () => void;

  lastSaved: Date | null;
  isSaving: boolean;
  setSaveState: (isSaving: boolean, lastSaved?: Date) => void;

  activeMasterTab: MasterModeTabId;
  setActiveMasterTab: (tab: MasterModeTabId) => void;

  factsEntityFilter: string | null;
  setFactsEntityFilter: (entityId: string | null) => void;
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
  hydrateFromScenario: (scenario) =>
    set((state) => ({
      newbieDraft: {
        ...state.newbieDraft,
        title: scenario.title ?? state.newbieDraft.title,
        logline: scenario.logline ?? state.newbieDraft.logline,
        genre_tags: scenario.genre_tags ?? state.newbieDraft.genre_tags,
        complexity_tier:
          scenario.complexity_tier ?? state.newbieDraft.complexity_tier,
        player_count_support:
          scenario.player_count_support ??
          state.newbieDraft.player_count_support,
        estimated_playtime:
          scenario.estimated_playtime ?? state.newbieDraft.estimated_playtime,
        cover_image_url:
          scenario.cover_image_url ?? state.newbieDraft.cover_image_url,
        setupInputs: scenario.setup_schema?.length
          ? scenario.setup_schema
          : state.newbieDraft.setupInputs,
        aiInstructions:
          scenario.narrator_persona ?? state.newbieDraft.aiInstructions,
      },
    })),
  resetDraft: () =>
    set({
      newbieDraft: defaultDraft,
      activeStep: 1,
      lastSaved: null,
      isSaving: false,
    }),

  lastSaved: null,
  isSaving: false,
  setSaveState: (isSaving, lastSaved) =>
    set((state) => ({
      isSaving,
      lastSaved: lastSaved !== undefined ? lastSaved : state.lastSaved,
    })),

  activeMasterTab: "entities",
  setActiveMasterTab: (tab) => set({ activeMasterTab: tab }),

  factsEntityFilter: null,
  setFactsEntityFilter: (entityId) => set({ factsEntityFilter: entityId }),
}));
