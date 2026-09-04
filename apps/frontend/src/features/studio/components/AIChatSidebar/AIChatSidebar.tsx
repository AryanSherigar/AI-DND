import React, { useEffect, useRef, useState } from "react";
import { useStudioStore, StoryCard } from "../../stores/studio.store";
import { useAssistantChat } from "../../hooks/useAssistantChat";
import {
  ActionBlock,
  ActionTarget,
  ACTION_TARGET_LABELS,
  ConflictModalState,
} from "../../types/assistant.types";
import { ActionCard } from "./ActionCard";
import { ConflictModal } from "./ConflictModal";
import { QuickPromptChips } from "./QuickPromptChips";
import { parseMessageSegments } from "./parseActionBlocks";

export interface AIChatSidebarProps {
  activeSection?: string;
}

interface ToastNotification {
  message: string;
  onUndo?: () => void;
}

const INITIAL_MODAL_STATE: ConflictModalState = {
  isOpen: false,
  target: "lore",
  targetLabel: "",
  existingValue: "",
  newValue: "",
};

export const AIChatSidebar: React.FC<AIChatSidebarProps> = ({
  activeSection = "meta",
}) => {
  const [input, setInput] = useState("");
  const [toast, setToast] = useState<ToastNotification | null>(null);
  const [modalState, setModalState] =
    useState<ConflictModalState>(INITIAL_MODAL_STATE);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, isStreaming, sendMessage, clearChat, stopGeneration } =
    useAssistantChat(activeSection);
  const { newbieDraft, updateNewbieDraft } = useStudioStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages]);

  const showToast = (message: string, onUndo?: () => void) => {
    setToast({ message, onUndo });
    setTimeout(() => setToast(null), 5000);
  };

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendMessage(input);
    setInput("");
  };

  const getExistingFieldValue = (target: ActionTarget): string => {
    switch (target) {
      case "title":
        return newbieDraft.title || "";
      case "logline":
        return newbieDraft.logline || "";
      case "lore":
        return newbieDraft.useSingleLorePrompt
          ? newbieDraft.singleLorePrompt || ""
          : newbieDraft.worldLore || "";
      case "opening_prompt":
        return newbieDraft.openingPrompt || "";
      case "conflict":
        return newbieDraft.mainConflict || "";
      case "style":
        return newbieDraft.narrativeStyle || "";
      case "instructions":
        return newbieDraft.aiInstructions || "";
      default:
        return "";
    }
  };

  const applyFieldUpdate = (target: ActionTarget, value: string) => {
    const prevValue = getExistingFieldValue(target);
    const targetLabel = ACTION_TARGET_LABELS[target];

    switch (target) {
      case "title":
        updateNewbieDraft({ title: value });
        break;
      case "logline":
        updateNewbieDraft({ logline: value });
        break;
      case "lore":
        if (newbieDraft.useSingleLorePrompt) {
          updateNewbieDraft({ singleLorePrompt: value });
        } else {
          updateNewbieDraft({ worldLore: value });
        }
        break;
      case "opening_prompt":
        updateNewbieDraft({ openingPrompt: value });
        break;
      case "conflict":
        updateNewbieDraft({ mainConflict: value, includeConflict: true });
        break;
      case "style":
        updateNewbieDraft({ narrativeStyle: value });
        break;
      case "instructions":
        updateNewbieDraft({ aiInstructions: value });
        break;
    }

    showToast(`Updated ${targetLabel}!`, () =>
      applyFieldUpdate(target, prevValue),
    );
  };

  const handleApplyStoryCard = (block: ActionBlock) => {
    const prevCards = [...(newbieDraft.storyCards || [])];
    const newCard: StoryCard = {
      id: String(Date.now()),
      type: block.metadata?.type || "Character",
      name: block.metadata?.name || "New Card",
      content: block.content,
    };
    updateNewbieDraft({ storyCards: [...prevCards, newCard] });
    showToast(`Added Card: ${newCard.name}!`, () => {
      updateNewbieDraft({ storyCards: prevCards });
    });
  };

  const handleApplyBlock = (block: ActionBlock) => {
    if (block.target === "story_card") {
      handleApplyStoryCard(block);
      return;
    }

    const existing = getExistingFieldValue(block.target);
    const label = ACTION_TARGET_LABELS[block.target] || block.target;

    if (existing.trim().length > 0) {
      setModalState({
        isOpen: true,
        target: block.target,
        targetLabel: label,
        existingValue: existing,
        newValue: block.content,
        metadata: block.metadata,
      });
    } else {
      applyFieldUpdate(block.target, block.content);
    }
  };

  const handleModalReplace = () => {
    applyFieldUpdate(modalState.target, modalState.newValue);
    setModalState(INITIAL_MODAL_STATE);
  };

  const handleModalAppend = () => {
    const combined = `${modalState.existingValue}\n\n${modalState.newValue}`;
    applyFieldUpdate(modalState.target, combined);
    setModalState(INITIAL_MODAL_STATE);
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950 font-sans text-zinc-300 relative">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-950">
        <span className="text-[11px] font-mono text-zinc-400 uppercase tracking-widest">
          AI Co-Author
        </span>
        <button
          type="button"
          onClick={clearChat}
          className="text-xs font-mono text-zinc-500 hover:text-zinc-200 uppercase tracking-wider transition-colors"
          title="Clear chat history"
        >
          Clear
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`px-3 py-2 rounded-none max-w-[95%] font-sans text-sm leading-relaxed border ${
                msg.role === "user"
                  ? "bg-zinc-900 text-zinc-200 border-zinc-800"
                  : "bg-zinc-950 text-zinc-100 border-zinc-800 shadow-sm"
              }`}
            >
              {msg.role === "assistant" ? (
                <div>
                  {parseMessageSegments(msg.content).map((segment, idx) =>
                    segment.type === "text" ? (
                      <span key={idx} className="whitespace-pre-wrap">
                        {segment.content}
                      </span>
                    ) : (
                      <ActionCard
                        key={idx}
                        block={segment.block}
                        onApply={handleApplyBlock}
                      />
                    ),
                  )}
                  {msg.content === "" && isStreaming && (
                    <span className="inline-block animate-pulse text-zinc-500 font-mono text-xs">
                      Thinking...
                    </span>
                  )}
                </div>
              ) : (
                <span className="whitespace-pre-wrap">{msg.content}</span>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Toast Banner */}
      {toast && (
        <div className="mx-3 mb-2 p-2 bg-amber-950/90 border border-amber-800/80 text-amber-200 text-xs flex items-center justify-between shadow-xl animate-in fade-in slide-in-from-bottom-2 duration-150">
          <span className="font-mono">{toast.message}</span>
          {toast.onUndo && (
            <button
              type="button"
              onClick={() => {
                toast.onUndo?.();
                setToast(null);
              }}
              className="text-amber-100 font-bold underline ml-2 uppercase text-[10px]"
            >
              Undo
            </button>
          )}
        </div>
      )}

      {/* Dynamic Quick Prompt Chips */}
      <QuickPromptChips
        activeSection={activeSection}
        onSelectPrompt={(p) => sendMessage(p)}
        disabled={isStreaming}
      />

      {/* Input Form */}
      <div className="p-3 border-t border-zinc-800 bg-zinc-950">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask anything about your scenario..."
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-none px-3 py-2 text-sm font-sans text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={stopGeneration}
              className="px-3 py-2 bg-red-950 text-red-200 hover:bg-red-900 border border-red-800 text-xs font-mono uppercase tracking-wider transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-2 bg-zinc-100 text-zinc-950 hover:bg-white rounded-none transition-colors border border-zinc-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Conflict Confirmation Modal */}
      <ConflictModal
        state={modalState}
        onReplace={handleModalReplace}
        onAppend={handleModalAppend}
        onClose={() => setModalState(INITIAL_MODAL_STATE)}
      />
    </div>
  );
};
