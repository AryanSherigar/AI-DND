import { create } from "zustand";
import {
  ActionMode,
  ChapterDelta,
  EBookTheme,
  PlaythroughData,
  PlaythroughEndedPayload,
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
import { ScenarioMood } from "@/shared/types/audio.types";
import { ambientSoundtrack } from "@/shared/lib/audio/ambient-soundtrack";
import { getMoodTrackUrl } from "@/shared/constants/audio";
import {
  MinigameEventPayload,
  MinigameResultPayload,
} from "@/shared/types/minigame.types";
import { MINIGAME_RESULT_ACTION_TEXT } from "../constants/minigame.constants";
import { READER_FONT_STORAGE_KEY } from "@/shared/constants/narration-fonts";
import { getPlaythrough } from "../api/playthroughs.api";

const TRS_BASE_URL = import.meta.env.VITE_TRS_URL || "http://localhost:8001";

// The POST /v1/turn body shared by a normal narrative action and a minigame
// result submission (TurnRequestInput on the TRS side — app/models/turn.py).
interface TurnStreamBody {
  playthrough_id: string;
  participant_id: string;
  action_text: string;
  action_kind: "narrative" | "minigame_result";
  action_mode: ActionMode;
  minigame_result?: MinigameResultPayload;
}

type MinigameResultStatus =
  "reconciling" | "submitting" | "retryable" | "terminal";

interface PendingMinigameResult {
  result: MinigameResultPayload;
  attempts: number;
  status: MinigameResultStatus;
  fallback_used: boolean;
}

const MAX_MINIGAME_RESULT_ATTEMPTS = 3;

function pendingMinigameFromServer(
  state: Record<string, unknown>,
): MinigameEventPayload | null {
  const pending = state._pending_minigame;
  if (!pending || typeof pending !== "object") return null;
  const payload = pending as Partial<MinigameEventPayload>;
  return typeof payload.minigame_id === "string"
    ? (payload as MinigameEventPayload)
    : null;
}

function isSamePendingAttempt(
  pending: MinigameEventPayload | null,
  result: MinigameResultPayload,
): boolean {
  if (!pending || pending.minigame_id !== result.minigame_id) return false;
  // Pending records written before attempt ids deliberately remain replayable.
  return !pending.attempt_id || pending.attempt_id === result.attempt_id;
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
  // Monotonic ownership token: callbacks from a cancelled/replaced SSE
  // connection must never overwrite newer play state.
  stream_generation: number;
  // Master mode: set when a `turn_summary` SSE event arrives, held until the
  // in-flight turn commits so the chapter summary strip only ever renders
  // from a turn already in playthrough.turns (never mid-stream).
  pending_chapter_delta: ChapterDelta | null;
  // Master mode: set when a `minigame` SSE event arrives, held until the
  // in-flight turn commits — mirrors pending_chapter_delta exactly — so the
  // overlay only ever appears once the triggering turn is fully committed.
  pending_minigame_trigger: MinigameEventPayload | null;
  // Master mode: set when a `playthrough_ended` SSE event arrives, held
  // until the in-flight turn commits — mirrors pending_chapter_delta exactly
  // — so the ending only ever renders once the triggering turn is committed.
  pending_playthrough_ended: PlaythroughEndedPayload | null;
  // Set when a `scene_image` SSE event arrives for a "see" action turn, held
  // until the in-flight turn commits — mirrors pending_chapter_delta exactly.
  pending_scene_image_url: string | null;
  // The minigame currently taking over the play surface full-screen, or one
  // resumed on reload from PlaythroughData.pending_minigame. Null renders
  // nothing (MinigameOverlay is an unconditional, guarded no-op mount).
  active_minigame: MinigameEventPayload | null;
  // Kept until the server's terminal "done" event confirms the pending
  // encounter was consumed. This makes failed submissions recoverable.
  pending_minigame_result: PendingMinigameResult | null;
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
  retryMinigameResult: () => void;
  submitMinigameTimeoutFallback: () => void;
  clearActiveMinigame: () => void;
  continueTurn: () => void;
  stopGeneration: () => void;
  retryLastTurn: () => void;
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
  stream_generation: 0,
  pending_chapter_delta: null,
  pending_minigame_trigger: null,
  pending_playthrough_ended: null,
  pending_scene_image_url: null,
  active_minigame: null,
  pending_minigame_result: null,
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
      const trackUrl = getMoodTrackUrl(initialMood, data.music_tracks);
      ambientSoundtrack.transitionTo(initialMood, trackUrl, true);
      // Resume a minigame the player left mid-resolution — reload must not
      // require a fresh SSE "minigame" event to show the overlay again.
    }
    // The API snapshot is authoritative. In particular, this reconciles an
    // ambiguous network failure: if the server consumed the result, dismiss
    // the retained local result; otherwise restore the unresolved encounter.
    if (data.pending_minigame) {
      set({ active_minigame: data.pending_minigame });
    } else {
      set({ active_minigame: null, pending_minigame_result: null });
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
    const trackUrl = getMoodTrackUrl(mood, get().playthrough?.music_tracks);
    ambientSoundtrack.transitionTo(mood, trackUrl, true);
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
    if (playthrough.ended_outcome_tag) return;
    submitTurn("Continue the story.");
  },

  submitTurn: (actionText: string) => {
    const { playthrough, active_minigame, active_mode } = get();
    if (!playthrough || !actionText.trim() || playthrough.is_spectator) return;
    if (active_minigame) return;
    if (!playthrough.participant_id) return;
    if (playthrough.ended_outcome_tag) return;

    get()._startTurnStream(
      {
        playthrough_id: playthrough.playthrough_id,
        participant_id: playthrough.participant_id,
        action_text: actionText,
        action_kind: "narrative",
        action_mode: active_mode,
      },
      actionText,
    );
  },

  submitMinigameResult: (result: MinigameResultPayload) => {
    const { playthrough, active_minigame, pending_minigame_result } = get();
    if (!playthrough || playthrough.is_spectator) return;
    if (!playthrough.participant_id) return;
    if (!active_minigame || active_minigame.minigame_id !== result.minigame_id)
      return;
    // Exactly once at the client boundary. The retry action below deliberately
    // resubmits this same immutable payload/attempt id.
    if (pending_minigame_result) return;

    const payload: MinigameResultPayload = {
      ...result,
      attempt_id: result.attempt_id ?? active_minigame.attempt_id,
    };
    set({
      pending_minigame_result: {
        result: payload,
        attempts: 1,
        status: "submitting",
        fallback_used: false,
      },
    });
    get()._startTurnStream(
      {
        playthrough_id: playthrough.playthrough_id,
        participant_id: playthrough.participant_id,
        action_text: MINIGAME_RESULT_ACTION_TEXT,
        action_kind: "minigame_result",
        action_mode: "do",
        minigame_result: payload,
      },
      MINIGAME_RESULT_ACTION_TEXT,
    );
  },

  retryMinigameResult: async () => {
    const { playthrough, pending_minigame_result } = get();
    if (
      !playthrough ||
      !playthrough.participant_id ||
      !pending_minigame_result ||
      pending_minigame_result.status !== "retryable" ||
      pending_minigame_result.attempts >= MAX_MINIGAME_RESULT_ATTEMPTS
    )
      return;
    // A dropped SSE can mean the server committed successfully. Never replay
    // an outcome until a fresh authoritative read proves this attempt is still
    // pending; this also makes the timeout fallback safe after a lost "done".
    set({
      pending_minigame_result: {
        ...pending_minigame_result,
        status: "reconciling",
      },
    });
    try {
      const serverPlaythrough = await getPlaythrough(
        playthrough.playthrough_id,
      );
      const serverPending = pendingMinigameFromServer(serverPlaythrough.state);
      void queryClient.setQueryData(
        ["playthrough", playthrough.playthrough_id],
        serverPlaythrough,
      );
      if (
        !isSamePendingAttempt(serverPending, pending_minigame_result.result)
      ) {
        set({
          active_minigame: serverPending,
          pending_minigame_result: null,
          is_narrating: false,
        });
        return;
      }
    } catch {
      // Reconciliation itself failed. Keep the outcome rather than gambling
      // on a duplicate POST; the player can safely retry this check.
      set((s) => ({
        pending_minigame_result:
          s.pending_minigame_result &&
          s.pending_minigame_result.result === pending_minigame_result.result
            ? { ...s.pending_minigame_result, status: "retryable" }
            : s.pending_minigame_result,
      }));
      return;
    }

    const attempts = pending_minigame_result.attempts + 1;
    set((s) => ({
      pending_minigame_result:
        s.pending_minigame_result &&
        s.pending_minigame_result.result === pending_minigame_result.result
          ? { ...s.pending_minigame_result, attempts, status: "submitting" }
          : s.pending_minigame_result,
    }));
    get()._startTurnStream(
      {
        playthrough_id: playthrough.playthrough_id,
        participant_id: playthrough.participant_id,
        action_text: MINIGAME_RESULT_ACTION_TEXT,
        action_kind: "minigame_result",
        action_mode: "do",
        minigame_result: pending_minigame_result.result,
      },
      MINIGAME_RESULT_ACTION_TEXT,
    );
  },

  submitMinigameTimeoutFallback: async () => {
    const { playthrough, pending_minigame_result } = get();
    if (
      !playthrough ||
      !playthrough.participant_id ||
      !pending_minigame_result ||
      pending_minigame_result.status !== "terminal" ||
      pending_minigame_result.fallback_used
    )
      return;
    set({
      pending_minigame_result: {
        ...pending_minigame_result,
        status: "reconciling",
      },
    });
    try {
      const serverPlaythrough = await getPlaythrough(
        playthrough.playthrough_id,
      );
      const serverPending = pendingMinigameFromServer(serverPlaythrough.state);
      void queryClient.setQueryData(
        ["playthrough", playthrough.playthrough_id],
        serverPlaythrough,
      );
      if (
        !isSamePendingAttempt(serverPending, pending_minigame_result.result)
      ) {
        set({
          active_minigame: serverPending,
          pending_minigame_result: null,
          is_narrating: false,
        });
        return;
      }
    } catch {
      set((s) => ({
        pending_minigame_result:
          s.pending_minigame_result &&
          s.pending_minigame_result.result === pending_minigame_result.result
            ? { ...s.pending_minigame_result, status: "terminal" }
            : s.pending_minigame_result,
      }));
      return;
    }
    const result = {
      ...pending_minigame_result.result,
      outcome_tag: "timeout" as const,
      score: undefined,
    };
    set({
      pending_minigame_result: {
        ...pending_minigame_result,
        result,
        attempts: 1,
        status: "submitting",
        fallback_used: true,
      },
    });
    get()._startTurnStream(
      {
        playthrough_id: playthrough.playthrough_id,
        participant_id: playthrough.participant_id,
        action_text: MINIGAME_RESULT_ACTION_TEXT,
        action_kind: "minigame_result",
        action_mode: "do",
        minigame_result: result,
      },
      MINIGAME_RESULT_ACTION_TEXT,
    );
  },

  clearActiveMinigame: () =>
    set({ active_minigame: null, pending_minigame_result: null }),

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
      pending_playthrough_ended: null,
      stream_generation: get().stream_generation + 1,
      pending_scene_image_url: null,
    });
  },

  retryLastTurn: () => {
    const { last_submitted_action, submitTurn } = get();
    if (last_submitted_action) {
      submitTurn(last_submitted_action);
    }
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

    const generation = get().stream_generation + 1;
    set({
      is_narrating: true,
      streaming_text: "",
      last_submitted_action: actionTextForLog,
      degraded_message: null,
      is_action_drawer_open: false,
      stream_generation: generation,
    });

    const token = useAuthStore.getState().accessToken;
    const requestId = generateRequestId();
    setCurrentRequestId(requestId);
    let reachedTerminalEvent = false;
    const ownsStream = () => get().stream_generation === generation;
    const failMinigameResult = (message: string) => {
      if (!ownsStream()) return;
      const pending = get().pending_minigame_result;
      if (body.action_kind !== "minigame_result" || !pending) {
        get()._degradeCurrentTurn(message);
        return;
      }
      const terminal =
        pending.fallback_used ||
        pending.attempts >= MAX_MINIGAME_RESULT_ATTEMPTS;
      set({
        is_narrating: false,
        streaming_text: "",
        cancel_stream_fn: null,
        pending_chapter_delta: null,
        pending_minigame_trigger: null,
        pending_playthrough_ended: null,
        degraded_message: null,
        pending_minigame_result: {
          ...pending,
          status: terminal ? "terminal" : "retryable",
        },
      });
    };
    const handlers: SSEHandlers = {
      onEvent: (eventName: string, data: string) => {
        if (!ownsStream()) return;
        if (eventName === "mood") {
          const mood = data as ScenarioMood;
          const trackUrl = getMoodTrackUrl(
            mood,
            get().playthrough?.music_tracks,
          );
          ambientSoundtrack.transitionTo(mood, trackUrl);
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
        } else if (eventName === "playthrough_ended") {
          // Buffered like pending_chapter_delta — does NOT set
          // reachedTerminalEvent, since "done" still follows normally.
          const payload = JSON.parse(data) as PlaythroughEndedPayload;
          set({ pending_playthrough_ended: payload });
        } else if (eventName === "scene_image") {
          // Buffered like pending_chapter_delta — does NOT set
          // reachedTerminalEvent, since "done" still follows normally.
          set({ pending_scene_image_url: data });
        } else if (eventName === "done") {
          reachedTerminalEvent = true;
          get()._commitStreamedTurn(actionTextForLog);
        } else if (eventName === "degraded") {
          reachedTerminalEvent = true;
          failMinigameResult(data);
        }
      },
      onError: () => {
        reachedTerminalEvent = true;
        failMinigameResult(
          "Connection lost. Your turn may not have saved — you can try again.",
        );
      },
      onClose: () => {
        // The connection ended without "done"/"degraded"/onError firing —
        // e.g. the server's stream broke mid-generation after headers were
        // already sent. Without this, the UI would hang on "thinking"
        // forever with no way for the player to recover.
        if (!reachedTerminalEvent) {
          failMinigameResult(
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

    if (ownsStream()) set({ cancel_stream_fn: cancelFn });
  },

  _commitStreamedTurn: (actionText: string) => {
    const {
      playthrough,
      streaming_text,
      active_mode,
      pending_chapter_delta,
      pending_minigame_trigger,
      pending_playthrough_ended,
      pending_scene_image_url,
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
      image_url: pending_scene_image_url ?? undefined,
    };

    set({
      playthrough: {
        ...playthrough,
        turns: [...playthrough.turns, newTurn],
        // Promote the buffered ending onto the committed playthrough — mirrors
        // pending_chapter_delta being attached to newTurn above. Falls back to
        // whatever was already there (null for an in-progress playthrough) when
        // nothing ended this turn.
        ended_outcome_tag:
          pending_playthrough_ended?.outcome_tag ??
          playthrough.ended_outcome_tag,
        ended_outcome_title:
          pending_playthrough_ended?.outcome_title ??
          playthrough.ended_outcome_title,
        ended_outcome_text:
          pending_playthrough_ended?.outcome_text ??
          playthrough.ended_outcome_text,
      },
      is_narrating: false,
      streaming_text: "",
      cancel_stream_fn: null,
      pending_chapter_delta: null,
      pending_minigame_trigger: null,
      pending_playthrough_ended: null,
      pending_minigame_result: null,
      pending_scene_image_url: null,
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
    void queryClient.invalidateQueries({
      queryKey: ["playthrough", playthrough.playthrough_id],
    });
  },

  _degradeCurrentTurn: (message: string) => {
    set({
      is_narrating: false,
      streaming_text: "",
      cancel_stream_fn: null,
      pending_chapter_delta: null,
      pending_minigame_trigger: null,
      pending_playthrough_ended: null,
      pending_scene_image_url: null,
      degraded_message: message,
    });
  },
}));

// Keep store active_mood always in sync with ambientSoundtrack
ambientSoundtrack.onMoodChange((mood) => {
  usePlayStore.setState({ active_mood: mood });
});
