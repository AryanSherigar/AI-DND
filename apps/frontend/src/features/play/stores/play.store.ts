import { create } from "zustand";
import {
  ActionMode,
  CharacterSetupField,
  PlaythroughData,
  TurnLogItem,
} from "../types/play.types";
import { createPostSSEConnection } from "@/shared/lib/sse-client";
import {
  generateRequestId,
  setCurrentRequestId,
} from "@/shared/lib/request-id";
import { useAuthStore } from "@/features/auth/stores/auth.store";
import { queryClient } from "@/shared/lib/query-client";

const TRS_BASE_URL = import.meta.env.VITE_TRS_URL || "http://localhost:8001";

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
  degraded_message: string | null;
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
  clearDegradedMessage: () => void;

  // Internal — not part of the public store surface; other files should not
  // call these directly. Exposed on the interface only because Zustand
  // actions call each other through get(), which requires them typed here.
  _commitStreamedTurn: (actionText: string) => void;
  _degradeCurrentTurn: (message: string) => void;
}

export const usePlayStore = create<PlayStoreState>((set, get) => ({
  playthrough: null,
  active_mode: "do",
  is_left_sidebar_open: true,
  is_right_sidebar_open: true,
  is_narrating: false,
  streaming_text: "",
  last_submitted_action: "",
  is_share_modal_open: false,
  is_warning_modal_open: false,
  is_end_modal_open: false,
  degraded_message: null,
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
  clearDegradedMessage: () => set({ degraded_message: null }),

  submitTurn: (actionText: string) => {
    const { playthrough, cancel_stream_fn } = get();
    if (!playthrough || !actionText.trim() || playthrough.is_spectator) return;
    if (!playthrough.participant_id) return;

    if (cancel_stream_fn) cancel_stream_fn();

    set({
      is_narrating: true,
      streaming_text: "",
      last_submitted_action: actionText,
      degraded_message: null,
    });

    const token = useAuthStore.getState().accessToken;
    const requestId = generateRequestId();
    setCurrentRequestId(requestId);
    let reachedTerminalEvent = false;
    const cancelFn = createPostSSEConnection(
      `${TRS_BASE_URL}/v1/turn`,
      {
        playthrough_id: playthrough.playthrough_id,
        participant_id: playthrough.participant_id,
        action_text: actionText,
      },
      token,
      {
        onEvent: (eventName: string, data: string) => {
          if (eventName === "narration") {
            set((s) => ({ streaming_text: s.streaming_text + data }));
          } else if (eventName === "done") {
            reachedTerminalEvent = true;
            get()._commitStreamedTurn(actionText);
          } else if (eventName === "degraded") {
            reachedTerminalEvent = true;
            get()._degradeCurrentTurn(data);
          }
        },
        onError: () => {
          reachedTerminalEvent = true;
          get()._degradeCurrentTurn(
            "Connection lost. Your turn may not have saved — you can try again.",
          );
        },
        onClose: () => {
          // The connection ended without "done"/"degraded"/onError firing —
          // e.g. the server's stream broke mid-generation after headers were
          // already sent. Without this, the UI would hang on "thinking"
          // forever with no way for the player to recover.
          if (!reachedTerminalEvent) {
            get()._degradeCurrentTurn(
              "The narrator stopped responding unexpectedly. Please try again.",
            );
          }
        },
      },
      requestId,
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

  // Internal helpers (not part of the public store surface — no consumer
  // outside this file should call these directly).
  _commitStreamedTurn: (actionText: string) => {
    const { playthrough, streaming_text, active_mode } = get();
    if (!playthrough) return;

    const newTurn: TurnLogItem = {
      id: `local-${Date.now()}`,
      turn_number: playthrough.turns.length + 1,
      action_mode: active_mode,
      action_text: actionText,
      narration_text: streaming_text,
      created_at: new Date().toISOString(),
    };

    set({
      playthrough: {
        ...playthrough,
        turns: [...playthrough.turns, newTurn],
      },
      is_narrating: false,
      streaming_text: "",
      cancel_stream_fn: null,
    });

    void queryClient.invalidateQueries({
      queryKey: ["playthrough-turns", playthrough.playthrough_id],
    });
  },

  _degradeCurrentTurn: (message: string) => {
    set({
      is_narrating: false,
      streaming_text: "",
      cancel_stream_fn: null,
      degraded_message: message,
    });
  },
}));
