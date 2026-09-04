import { useCallback, useEffect, useRef, useState } from "react";
import { createPostSSEConnection } from "@/shared/lib/sse-client";
import { useAuthStore } from "@/features/auth/stores/auth.store";
import { useStudioStore } from "../stores/studio.store";
import { AssistantMessage } from "../types/assistant.types";

const STORAGE_KEY = "aidnd_studio_assistant_chat";
const TRS_BASE_URL = import.meta.env.VITE_TRS_URL || "http://localhost:8001";

const DEFAULT_WELCOME: AssistantMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Greetings, creator. I am your world-building co-author. Need a compelling premise, unique factions, evocative lore, or narrative rules? Tell me what you envision or click any starter prompt below!",
  timestamp: Date.now(),
};

const loadInitialMessages = (): AssistantMessage[] => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return [DEFAULT_WELCOME];
    const parsed = JSON.parse(saved);
    return Array.isArray(parsed) && parsed.length > 0
      ? parsed
      : [DEFAULT_WELCOME];
  } catch {
    return [DEFAULT_WELCOME];
  }
};

export const useAssistantChat = (activeSection: string = "meta") => {
  const [messages, setMessages] =
    useState<AssistantMessage[]>(loadInitialMessages);
  const [isStreaming, setIsStreaming] = useState(false);
  const cancelStreamRef = useRef<(() => void) | null>(null);
  const newbieDraft = useStudioStore((s) => s.newbieDraft);
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // Storage quota or private browsing
    }
  }, [messages]);

  const clearChat = useCallback(() => {
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    setMessages([DEFAULT_WELCOME]);
    setIsStreaming(false);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const stopGeneration = useCallback(() => {
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const buildPayload = useCallback(
    (nextMessages: AssistantMessage[]) => ({
      messages: nextMessages.map((m) => ({
        role: m.role,
        content: m.content,
      })),
      draft_context: {
        title: newbieDraft.title || "",
        logline: newbieDraft.logline || "",
        genre_tags: newbieDraft.genre_tags || [],
        complexity_tier: newbieDraft.complexity_tier || "newbie",
        player_count_support: newbieDraft.player_count_support || "solo",
        estimated_playtime: newbieDraft.estimated_playtime || "",
        world_lore: newbieDraft.worldLore || "",
        opening_prompt: newbieDraft.openingPrompt || "",
        main_conflict: newbieDraft.mainConflict || "",
        single_lore_prompt: newbieDraft.singleLorePrompt || "",
        story_cards: newbieDraft.storyCards || [],
        ai_instructions: newbieDraft.aiInstructions || "",
        narrative_style: newbieDraft.narrativeStyle || "",
        active_section: activeSection,
      },
    }),
    [newbieDraft, activeSection],
  );

  const sendMessage = useCallback(
    (promptText: string) => {
      const trimmed = promptText.trim();
      if (!trimmed || isStreaming) return;

      const userMsg: AssistantMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
        timestamp: Date.now(),
      };
      const assistantId = `assistant-${Date.now()}`;
      const placeholderAssistant: AssistantMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };

      const updatedHistory = [...messages, userMsg];
      setMessages([...updatedHistory, placeholderAssistant]);
      setIsStreaming(true);

      const url = `${TRS_BASE_URL}/v1/studio/assistant`;
      const payload = buildPayload(updatedHistory);

      const cancelFn = createPostSSEConnection(url, payload, accessToken, {
        onEvent: (event, data) => {
          if (event === "chunk") {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, content: msg.content + data }
                  : msg,
              ),
            );
          } else if (event === "done") {
            setIsStreaming(false);
          } else if (event === "error") {
            setIsStreaming(false);
            let errorText = "AI assistant is temporarily unavailable.";
            try {
              const parsed = JSON.parse(data);
              if (parsed.detail) errorText = parsed.detail;
            } catch {
              if (data) errorText = data;
            }
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, content: `⚠️ ${errorText}` }
                  : msg,
              ),
            );
          }
        },
        onError: () => {
          setIsStreaming(false);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId && msg.content === ""
                ? {
                    ...msg,
                    content:
                      "⚠️ Connection error. Please ensure the backend service is running and try again.",
                  }
                : msg,
            ),
          );
        },
        onClose: () => {
          setIsStreaming(false);
        },
      });

      cancelStreamRef.current = cancelFn;
    },
    [messages, isStreaming, accessToken, buildPayload],
  );

  return {
    messages,
    isStreaming,
    sendMessage,
    clearChat,
    stopGeneration,
  };
};
