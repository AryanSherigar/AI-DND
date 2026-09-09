import React, { useEffect, useRef, useState } from "react";
import { useStudioStore, StoryCard } from "../../stores/studio.store";
import { useAssistantChat } from "../../hooks/useAssistantChat";
import { useMasterActionApplier } from "../../hooks/useMasterActionApplier";
import {
  ActionBlock,
  ActionTarget,
  ACTION_TARGET_LABELS,
  ConflictModalState,
  DestructiveConfirmState,
  isDeleteActionBlock,
  MASTER_EXPRESSION_TARGETS,
} from "../../types/assistant.types";
import { ActionCard } from "./ActionCard";
import { ConflictModal } from "./ConflictModal";
import { DestructiveConfirmModal } from "./DestructiveConfirmModal";
import {
  ExpressionReviewModal,
  ExpressionReviewTarget,
} from "./ExpressionReviewModal";
import { QuickPromptChips } from "./QuickPromptChips";
import { parseMessageSegments, MessageSegment } from "./parseActionBlocks";

export interface AIChatSidebarProps {
  activeSection?: string;
  scenarioId?: string;
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

const INITIAL_DESTRUCTIVE_STATE: DestructiveConfirmState = {
  isOpen: false,
  block: null,
  description: "",
};

interface ReviewState {
  target: ExpressionReviewTarget;
  draft: Record<string, unknown> | null;
  key: string;
}

const parseJsonSafe = (content: string): Record<string, unknown> | null => {
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
};

export const AIChatSidebar: React.FC<AIChatSidebarProps> = ({
  activeSection = "meta",
  scenarioId,
}) => {
  const [input, setInput] = useState("");
  const [toast, setToast] = useState<ToastNotification | null>(null);
  const [modalState, setModalState] =
    useState<ConflictModalState>(INITIAL_MODAL_STATE);
  const [destructiveState, setDestructiveState] =
    useState<DestructiveConfirmState>(INITIAL_DESTRUCTIVE_STATE);
  const [reviewState, setReviewState] = useState<ReviewState | null>(null);
  const [appliedKeys, setAppliedKeys] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const mode = useStudioStore((s) => s.mode);
  const { newbieDraft, updateNewbieDraft } = useStudioStore();
  const {
    messages,
    isStreaming,
    sendMessage,
    clearChat,
    stopGeneration,
    reportApplyError,
    blockValidationByMessage,
  } = useAssistantChat(activeSection, mode, scenarioId ?? null);
  const [isConfirmingClear, setIsConfirmingClear] = useState(false);
  const masterApplier = useMasterActionApplier(
    scenarioId ?? null,
    reportApplyError,
  );

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
    setIsConfirmingClear(false);
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

  const handleNewbieApplyBlock = (block: ActionBlock) => {
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

  const markApplied = (key: string) =>
    setAppliedKeys((prev) => new Set(prev).add(key));

  const buildDestructiveDescription = (block: ActionBlock): string => {
    const label = ACTION_TARGET_LABELS[block.target] || block.target;
    return `This will permanently delete this ${label.toLowerCase()} from your scenario. This cannot be undone.`;
  };

  const handleMasterApplyBlock = async (block: ActionBlock, key: string) => {
    if (isDeleteActionBlock(block)) {
      setDestructiveState({
        isOpen: true,
        block,
        description: buildDestructiveDescription(block),
      });
      return;
    }
    if (MASTER_EXPRESSION_TARGETS.includes(block.target)) {
      setReviewState({
        target: block.target as ExpressionReviewTarget,
        draft: parseJsonSafe(block.content),
        key,
      });
      return;
    }
    await masterApplier.applyBlock(block);
    markApplied(key);
  };

  const handleApplyBlock = (block: ActionBlock, key: string) => {
    if (mode === "master") {
      void handleMasterApplyBlock(block, key);
    } else {
      handleNewbieApplyBlock(block);
      markApplied(key);
    }
  };

  const handleApplyAll = async (
    blocks: { block: ActionBlock; key: string }[],
  ) => {
    const applicable = blocks.filter(
      (b) =>
        !isDeleteActionBlock(b.block) &&
        !MASTER_EXPRESSION_TARGETS.includes(b.block.target),
    );
    await masterApplier.applyBatch(applicable.map((b) => b.block));
    applicable.forEach((b) => markApplied(b.key));
  };

  const handleDestructiveConfirm = async () => {
    const { block } = destructiveState;
    setDestructiveState(INITIAL_DESTRUCTIVE_STATE);
    if (!block) return;
    await masterApplier.applyDestructive(block);
  };

  const handleReviewApplied = () => {
    if (reviewState) markApplied(reviewState.key);
    setReviewState(null);
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

  const getValidationErrors = (
    messageId: string,
    actionOrdinal: number,
  ): string[] | undefined =>
    blockValidationByMessage[messageId]?.find((v) => v.index === actionOrdinal)
      ?.errors;

  const renderMessageSegments = (
    messageId: string,
    segments: MessageSegment[],
  ) => {
    let actionOrdinal = -1;
    const rendered = segments.map((segment, idx) => {
      if (segment.type === "text") {
        return (
          <span key={idx} className="whitespace-pre-wrap">
            {segment.content}
          </span>
        );
      }
      actionOrdinal += 1;
      const ordinal = actionOrdinal;
      const key = `${messageId}:${ordinal}`;
      return (
        <ActionCard
          key={idx}
          block={segment.block}
          isApplied={appliedKeys.has(key)}
          validationErrors={getValidationErrors(messageId, ordinal)}
          onApply={(block) => handleApplyBlock(block, key)}
        />
      );
    });

    const actionEntries = segments
      .filter(
        (s): s is Extract<MessageSegment, { type: "action" }> =>
          s.type === "action",
      )
      .map((segment, ordinal) => ({
        block: segment.block,
        key: `${messageId}:${ordinal}`,
      }));
    const showApplyAll = mode === "master" && actionEntries.length > 1;

    return (
      <div>
        {rendered}
        {showApplyAll && (
          <button
            type="button"
            onClick={() => handleApplyAll(actionEntries)}
            className="rounded-md mt-1 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider bg-accent/10 text-accent hover:bg-accent/20 border border-accent/40 transition-colors"
          >
            Apply All ({actionEntries.length})
          </button>
        )}
      </div>
    );
  };

  const handleClearChat = () => {
    if (!isConfirmingClear) {
      setIsConfirmingClear(true);
      return;
    }
    clearChat();
    setIsConfirmingClear(false);
  };

  return (
    <div className="flex flex-col h-full bg-surface-inset font-sans text-content-muted relative">
      {/* Clear Chat Control */}
      <div className="flex items-center justify-end gap-2 px-3 py-2 border-b border-border-subtle">
        {isConfirmingClear && (
          <button
            type="button"
            onClick={() => setIsConfirmingClear(false)}
            className="text-[10px] font-mono uppercase tracking-wider text-content-faint hover:text-content-muted"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={handleClearChat}
          className={`rounded-md px-2 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
            isConfirmingClear
              ? "bg-danger/10 text-danger border border-danger/40 hover:bg-danger/20"
              : "text-content-faint hover:text-content-muted"
          }`}
        >
          {isConfirmingClear ? "Confirm clear?" : "Clear chat"}
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
              className={`px-3 py-2 rounded-md max-w-[95%] font-sans text-sm leading-relaxed border ${
                msg.role === "user"
                  ? "bg-surface text-content border-border-subtle"
                  : "bg-surface-inset text-content border-border-subtle shadow-sm"
              }`}
            >
              {msg.role === "assistant" ? (
                <div>
                  {renderMessageSegments(
                    msg.id,
                    parseMessageSegments(msg.content),
                  )}
                  {msg.content === "" && isStreaming && (
                    <span className="inline-block animate-pulse text-content-faint font-mono text-xs">
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
        <div className="rounded-md mx-3 mb-2 p-2 bg-accent/10 border border-accent/40 text-accent text-xs flex items-center justify-between shadow-xl animate-in fade-in slide-in-from-bottom-2 duration-150">
          <span className="font-mono">{toast.message}</span>
          {toast.onUndo && (
            <button
              type="button"
              onClick={() => {
                toast.onUndo?.();
                setToast(null);
              }}
              className="text-accent font-bold underline ml-2 uppercase text-[10px]"
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
        mode={mode}
      />

      {/* Input Form */}
      <div className="p-3 border-t border-border-subtle bg-surface-inset">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask anything about your scenario..."
            className="flex-1 bg-surface border border-border-subtle rounded-md px-3 py-2 text-sm font-sans text-content placeholder:text-content-faint focus:outline-none focus:border-border-strong"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={stopGeneration}
              className="rounded-md px-3 py-2 bg-danger/10 text-danger hover:bg-danger/20 border border-danger/40 text-xs font-mono uppercase tracking-wider transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-2 bg-content text-surface hover:bg-white rounded-md transition-colors border border-content disabled:opacity-40 disabled:cursor-not-allowed"
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

      {/* Destructive Action Confirmation Modal */}
      <DestructiveConfirmModal
        state={destructiveState}
        onConfirm={() => void handleDestructiveConfirm()}
        onClose={() => setDestructiveState(INITIAL_DESTRUCTIVE_STATE)}
      />

      {/* Expression-Tree Review Modal (conditions/invariants/end conditions) */}
      {scenarioId && (
        <ExpressionReviewModal
          target={reviewState?.target ?? null}
          scenarioId={scenarioId}
          draft={reviewState?.draft ?? null}
          onClose={() => setReviewState(null)}
          onApplied={handleReviewApplied}
        />
      )}
    </div>
  );
};
