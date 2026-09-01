import { create } from "zustand";
import {
  ActionMode,
  CharacterSetupField,
  PlaythroughData,
  TurnLogItem,
} from "../types/play.types";
import {
  INITIAL_MOCK_PLAYTHROUGH,
  simulateTokenStream,
} from "../mock/playthroughMock";

interface PlayStoreState {
  playthrough: PlaythroughData | null;
  active_mode: ActionMode;
  is_left_sidebar_open: boolean;
  is_right_sidebar_open: boolean;
  is_narrating: boolean;
  streaming_text: string;
  last_submitted_action: string;
  is_share_modal_open: boolean;
  is_warning_modal_open: boolean;
  is_end_modal_open: boolean;
  cancel_stream_fn: (() => void) | null;

  // Actions
  setPlaythrough: (data: PlaythroughData) => void;
  setActiveMode: (mode: ActionMode) => void;
  toggleLeftSidebar: () => void;
  toggleRightSidebar: () => void;
  setLeftSidebarOpen: (isOpen: boolean) => void;
  setRightSidebarOpen: (isOpen: boolean) => void;
  openShareModal: () => void;
  closeShareModal: () => void;
  openWarningModal: () => void;
  closeWarningModal: () => void;
  openEndModal: () => void;
  closeEndModal: () => void;
  submitTurn: (actionText: string) => void;
  stopGeneration: () => void;
  retryLastTurn: () => void;
  editLastAction: () => string;
  updateCharacterFields: (updatedFields: CharacterSetupField[]) => void;
}

export const usePlayStore = create<PlayStoreState>((set, get) => ({
  playthrough: INITIAL_MOCK_PLAYTHROUGH,
  active_mode: "do",
  is_left_sidebar_open: true,
  is_right_sidebar_open: true,
  is_narrating: false,
  streaming_text: "",
  last_submitted_action: "",
  is_share_modal_open: false,
  is_warning_modal_open: false,
  is_end_modal_open: false,
  cancel_stream_fn: null,

  setPlaythrough: (data: PlaythroughData) => set({ playthrough: data }),
  setActiveMode: (mode: ActionMode) => set({ active_mode: mode }),
  toggleLeftSidebar: () =>
    set((s) => ({ is_left_sidebar_open: !s.is_left_sidebar_open })),
  toggleRightSidebar: () =>
    set((s) => ({ is_right_sidebar_open: !s.is_right_sidebar_open })),
  setLeftSidebarOpen: (isOpen: boolean) =>
    set({ is_left_sidebar_open: isOpen }),
  setRightSidebarOpen: (isOpen: boolean) =>
    set({ is_right_sidebar_open: isOpen }),
  openShareModal: () => set({ is_share_modal_open: true }),
  closeShareModal: () => set({ is_share_modal_open: false }),
  openWarningModal: () => set({ is_warning_modal_open: true }),
  closeWarningModal: () => set({ is_warning_modal_open: false }),
  openEndModal: () => set({ is_end_modal_open: true }),
  closeEndModal: () => set({ is_end_modal_open: false }),

  submitTurn: (actionText: string) => {
    const { playthrough, active_mode, cancel_stream_fn } = get();
    if (!playthrough || !actionText.trim()) return;

    if (cancel_stream_fn) {
      cancel_stream_fn();
    }

    set({
      is_narrating: true,
      streaming_text: "",
      last_submitted_action: actionText,
    });

    const cancelFn = simulateTokenStream(
      active_mode,
      (token: string) => {
        set((s) => ({ streaming_text: s.streaming_text + token }));
      },
      () => {
        const finalNarration = get().streaming_text;
        const currentPlaythrough = get().playthrough;
        if (!currentPlaythrough) return;

        const nextTurnNumber = currentPlaythrough.turns.length + 1;
        const newTurn: TurnLogItem = {
          id: `turn-${Date.now()}`,
          turn_number: nextTurnNumber,
          action_mode: active_mode,
          action_text: actionText,
          narration_text: finalNarration,
          created_at: new Date().toISOString(),
        };

        set({
          playthrough: {
            ...currentPlaythrough,
            turns: [...currentPlaythrough.turns, newTurn],
          },
          is_narrating: false,
          streaming_text: "",
          cancel_stream_fn: null,
        });
      },
    );

    set({ cancel_stream_fn: cancelFn });
  },

  stopGeneration: () => {
    const { cancel_stream_fn } = get();
    if (cancel_stream_fn) {
      cancel_stream_fn();
    }
    set({
      is_narrating: false,
      streaming_text: "",
      cancel_stream_fn: null,
    });
  },

  retryLastTurn: () => {
    const { last_submitted_action, submitTurn } = get();
    if (last_submitted_action) {
      submitTurn(last_submitted_action);
    }
  },

  editLastAction: () => {
    const { playthrough, stopGeneration } = get();
    stopGeneration();

    if (!playthrough || playthrough.turns.length === 0) return "";

    const turnsCopy = [...playthrough.turns];
    const lastTurn = turnsCopy.pop();
    if (!lastTurn) return "";

    set({
      playthrough: {
        ...playthrough,
        turns: turnsCopy,
      },
      active_mode: lastTurn.action_mode,
      last_submitted_action: lastTurn.action_text,
    });

    return lastTurn.action_text;
  },

  updateCharacterFields: (updatedFields: CharacterSetupField[]) => {
    const { playthrough } = get();
    if (!playthrough) return;

    set({
      playthrough: {
        ...playthrough,
        custom_fields: updatedFields,
      },
      is_warning_modal_open: false,
    });
  },
}));
