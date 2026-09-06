import { create } from "zustand";
import {
  ActionMode,
  ChapterDelta,
  EBookTheme,
  PlaythroughData,
  TurnLogItem,
} from "../types/play.types";
import { TurnSummaryEventPayload } from "../types/turnSummary.types";
import { mapTurnSummaryEvent } from "../utils/chapterDelta";
import { createPostSSEConnection, SSEHandlers } from "@/shared/lib/sse-client";
import {
  generateRequestId,
  setCurrentRequestId,
} from "@/shared/lib/request-id";
import { useAuthStore } from "@/features/auth/stores/auth.store";
import { queryClient } from "@/shared/lib/query-client";
import { ScenarioMood } from "../types/audio.types";
import { ambientSoundtrack } from "@/shared/lib/audio/ambient-soundtrack";
import {
  MinigameEventPayload,
  MinigameResultPayload,
} from "@/shared/types/minigame.types";
import { MINIGAME_RESULT_ACTION_TEXT } from "../constants/minigame.constants";
import { READER_FONT_STORAGE_KEY } from "@/shared/constants/narration-fonts";

const TRS_BASE_URL = import.meta.env.VITE_TRS_URL || "http://localhost:8001";

// The POST /v1/turn body shared by a normal narrative action and a minigame
// result submission (TurnRequestInput on the TRS side — app/models/turn.py).
interface TurnStreamBody {
  playthrough_id: string;
  participant_id: string;
  action_text: string;
  action_kind: "narrative" | "minigame_result";
  minigame_result?: MinigameResultPayload;
}

interface PlayStoreState {
  playthrough: PlaythroughData | null;
  active_mode: ActionMode;
  ebook_theme: EBookTheme;
  is_left_sidebar_open: boolean;
  is_right_sidebar_open: boolean;
  is_action_drawer_open: boolean;
  is_chronicle_modal_open: boolean;
  is_narrating: boolean;
  streaming_text: string;
  last_submitted_action: string;
  degraded_message: string | null;
  cancel_stream_fn: (() => void) | null;
  // Master mode: set when a `turn_summary` SSE event arrives, held until the
  // in-flight turn commits so the chapter summary strip only ever renders
  // from a turn already in playthrough.turns (never mid-stream).
  pending_chapter_delta: ChapterDelta | null;
  // Master mode: set when a `minigame` SSE event arrives, held until the
  // in-flight turn commits — mirrors pending_chapter_delta exactly — so the
  // overlay only ever appears once the triggering turn is fully committed.
  pending_minigame_trigger: MinigameEventPayload | null;
  // The minigame currently taking over the play surface full-screen, or one
  // resumed on reload from PlaythroughData.pending_minigame. Null renders
  // nothing (MinigameOverlay is an unconditional, guarded no-op mount).
  active_minigame: MinigameEventPayload | null;
  reader_font_override: string | null;

  // Actions
  setPlaythrough: (data: PlaythroughData) => void;
  setReaderFontOverride: (fontId: string | null) => void;
  setActiveMode: (mode: ActionMode) => void;
  setEBookTheme: (theme: EBookTheme) => void;
  toggleEBookTheme: () => void;
  toggleLeftSidebar: () => void;
  toggleRightSidebar: () => void;
  setLeftSidebarOpen: (isOpen: boolean) => void;
  setRightSidebarOpen: (isOpen: boolean) => void;
  openActionDrawer: () => void;
  closeActionDrawer: () => void;
  toggleActionDrawer: () => void;
  openChronicleModal: () => void;
  closeChronicleModal: () => void;
  submitTurn: (actionText: string) => void;
  submitMinigameResult: (result: MinigameResultPayload) => void;
  clearActiveMinigame: () => void;
  continueTurn: () => void;
  stopGeneration: () => void;
  retryLastTurn: () => void;
  editLastAction: () => string;
  clearDegradedMessage: () => void;
  active_mood: ScenarioMood;
  audio_volume: number;
  is_audio_muted: boolean;
  setAudioVolume: (volume: number) => void;
  toggleAudioMute: () => void;
  setMood: (mood: ScenarioMood) => void;

  // Internal — not part of the public store surface; other files should not
  // call these directly. Exposed on the interface only because Zustand
  // actions call each other through get(), which requires them typed here.
  _startTurnStream: (body: TurnStreamBody, actionTextForLog: string) => void;
  _commitStreamedTurn: (actionText: string) => void;
  _degradeCurrentTurn: (message: string) => void;
}

export const usePlayStore = create<PlayStoreState>((set, get) => ({
  playthrough: null,
  active_mode: "do",
  ebook_theme: "dark-velvet",
  is_left_sidebar_open: true,
  is_right_sidebar_open: true,
  is_action_drawer_open: false,
  is_chronicle_modal_open: false,
  is_narrating: false,
  streaming_text: "",
  last_submitted_action: "",
  degraded_message: null,
  cancel_stream_fn: null,
  pending_chapter_delta: null,
  pending_minigame_trigger: null,
  active_minigame: null,
  reader_font_override:
    typeof window !== "undefined"
      ? localStorage.getItem(READER_FONT_STORAGE_KEY)
      : null,
  active_mood: "peaceful",
  audio_volume: ambientSoundtrack.getVolume(),
  is_audio_muted: ambientSoundtrack.getIsMuted(),

  setReaderFontOverride: (fontId: string | null) => {
    if (typeof window !== "undefined") {
      if (fontId) {
        localStorage.setItem(READER_FONT_STORAGE_KEY, fontId);
      } else {
        localStorage.removeItem(READER_FONT_STORAGE_KEY);
      }
    }
    set({ reader_font_override: fontId });
  },

  setPlaythrough: (data: PlaythroughData) => {
    const prevPlaythrough = get().playthrough;
    const isNewPlaythrough =
      !prevPlaythrough ||
      prevPlaythrough.playthrough_id !== data.playthrough_id;
    set({ playthrough: data });

    if (isNewPlaythrough) {
      const initialMood = data.initial_mood || "peaceful";
      ambientSoundtrack.transitionTo(initialMood, true);
      // Resume a minigame the player left mid-resolution — reload must not
      // require a fresh SSE "minigame" event to show the overlay again.
      if (data.pending_minigame) {
        set({ active_minigame: data.pending_minigame });
      }
    }
  },
  setAudioVolume: (vol: number) => {
    ambientSoundtrack.setVolume(vol);
    set({ audio_volume: ambientSoundtrack.getVolume() });
  },
  toggleAudioMute: () => {
    const isMuted = ambientSoundtrack.toggleMute();
    set({ is_audio_muted: isMuted });
  },
  setMood: (mood: ScenarioMood) => {
    ambientSoundtrack.transitionTo(mood, true);
  },
  setActiveMode: (mode: ActionMode) => set({ active_mode: mode }),
  setEBookTheme: (theme: EBookTheme) => set({ ebook_theme: theme }),
  toggleEBookTheme: () =>
    set((s) => ({
      ebook_theme:
        s.ebook_theme === "dark-velvet" ? "antique-sepia" : "dark-velvet",
    })),
  toggleLeftSidebar: () =>
    set((s) => ({ is_left_sidebar_open: !s.is_left_sidebar_open })),
  toggleRightSidebar: () =>
    set((s) => ({ is_right_sidebar_open: !s.is_right_sidebar_open })),
  setLeftSidebarOpen: (isOpen: boolean) =>
    set({ is_left_sidebar_open: isOpen }),
  setRightSidebarOpen: (isOpen: boolean) =>
    set({ is_right_sidebar_open: isOpen }),
  openActionDrawer: () => set({ is_action_drawer_open: true }),
  closeActionDrawer: () => set({ is_action_drawer_open: false }),
  toggleActionDrawer: () =>
    set((s) => ({ is_action_drawer_open: !s.is_action_drawer_open })),
  openChronicleModal: () => set({ is_chronicle_modal_open: true }),
  closeChronicleModal: () => set({ is_chronicle_modal_open: false }),
  clearDegradedMessage: () => set({ degraded_message: null }),

  continueTurn: () => {
    const { playthrough, is_narrating, submitTurn } = get();
    if (!playthrough || is_narrating || playthrough.is_spectator) return;
    submitTurn("Continue the story.");
  },

  submitTurn: (actionText: string) => {
    const { playthrough } = get();
    if (!playthrough || !actionText.trim() || playthrough.is_spectator) return;
    if (!playthrough.participant_id) return;

    get()._startTurnStream(
      {
        playthrough_id: playthrough.playthrough_id,
        participant_id: playthrough.participant_id,
        action_text: actionText,
        action_kind: "narrative",
      },
      actionText,
    );
  },

  submitMinigameResult: (result: MinigameResultPayload) => {
    const { playthrough } = get();
    if (!playthrough || playthrough.is_spectator) return;
    if (!playthrough.participant_id) return;

    get()._startTurnStream(
      {
        playthrough_id: playthrough.playthrough_id,
        participant_id: playthrough.participant_id,
        action_text: MINIGAME_RESULT_ACTION_TEXT,
        action_kind: "minigame_result",
        minigame_result: result,
      },
      MINIGAME_RESULT_ACTION_TEXT,
    );
  },

  clearActiveMinigame: () => set({ active_minigame: null }),

  stopGeneration: () => {
    const { cancel_stream_fn } = get();
    if (cancel_stream_fn) {
      cancel_stream_fn();
    }
    set({
      is_narrating: false,
      streaming_text: "",
      cancel_stream_fn: null,
      pending_chapter_delta: null,
      pending_minigame_trigger: null,
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

  // Internal helpers (not part of the public store surface — no consumer
  // outside this file should call these directly).
  //
  // Shared SSE-stream machinery for both a normal narrative action and a
  // minigame result submission — the only difference between the two is the
  // POST body and the actionText used for the local turn log entry, so both
  // public actions build a TurnStreamBody and delegate here rather than each
  // wiring up createPostSSEConnection/onEvent themselves.
  _startTurnStream: (body: TurnStreamBody, actionTextForLog: string) => {
    const { cancel_stream_fn } = get();
    if (cancel_stream_fn) cancel_stream_fn();

    set({
      is_narrating: true,
      streaming_text: "",
      last_submitted_action: actionTextForLog,
      degraded_message: null,
      is_action_drawer_open: false,
    });

    const token = useAuthStore.getState().accessToken;
    const requestId = generateRequestId();
    setCurrentRequestId(requestId);
    let reachedTerminalEvent = false;
    const handlers: SSEHandlers = {
      onEvent: (eventName: string, data: string) => {
        if (eventName === "mood") {
          const mood = data as ScenarioMood;
          ambientSoundtrack.transitionTo(mood);
        } else if (eventName === "narration") {
          set((s) => ({ streaming_text: s.streaming_text + data }));
        } else if (eventName === "turn_summary") {
          const payload = JSON.parse(data) as TurnSummaryEventPayload;
          set((s) => ({
            pending_chapter_delta: mapTurnSummaryEvent(payload),
            playthrough: s.playthrough && {
              ...s.playthrough,
              active_conditions: payload.active_conditions,
            },
          }));
        } else if (eventName === "minigame") {
          // Buffered like pending_chapter_delta — does NOT set
          // reachedTerminalEvent, since "done" still follows normally.
          const payload = JSON.parse(data) as MinigameEventPayload;
          set({ pending_minigame_trigger: payload });
        } else if (eventName === "done") {
          reachedTerminalEvent = true;
          get()._commitStreamedTurn(actionTextForLog);
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
    };

    const cancelFn = createPostSSEConnection(
      `${TRS_BASE_URL}/v1/turn`,
      body,
      token,
      handlers,
      requestId,
    );

    set({ cancel_stream_fn: cancelFn });
  },

  _commitStreamedTurn: (actionText: string) => {
    const {
      playthrough,
      streaming_text,
      active_mode,
      pending_chapter_delta,
      pending_minigame_trigger,
    } = get();
    if (!playthrough) return;

    const newTurn: TurnLogItem = {
      id: `local-${Date.now()}`,
      turn_number: playthrough.turns.length + 1,
      action_mode: active_mode,
      action_text: actionText,
      narration_text: streaming_text,
      created_at: new Date().toISOString(),
      chapter_delta: pending_chapter_delta ?? undefined,
    };

    set({
      playthrough: {
        ...playthrough,
        turns: [...playthrough.turns, newTurn],
      },
      is_narrating: false,
      streaming_text: "",
      cancel_stream_fn: null,
      pending_chapter_delta: null,
      pending_minigame_trigger: null,
      // Promote the buffered trigger into the overlay-driving field now that
      // the triggering turn is fully committed — mirrors pending_chapter_delta
      // being attached to newTurn above. When nothing triggered this turn,
      // this resolves to null, which is always correct here: a normal turn
      // never has an active_minigame set (submission is gated on none being
      // pending), and a minigame-result turn's overlay was already cleared
      // via clearActiveMinigame() before this stream started.
      active_minigame: pending_minigame_trigger ?? null,
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
      pending_chapter_delta: null,
      pending_minigame_trigger: null,
      degraded_message: message,
    });
  },
}));

// Keep store active_mood always in sync with ambientSoundtrack
ambientSoundtrack.onMoodChange((mood) => {
  usePlayStore.setState({ active_mood: mood });
});
