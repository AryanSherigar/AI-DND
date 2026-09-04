import React, { useState } from "react";
import { ActionBlock, ACTION_TARGET_LABELS } from "../../types/assistant.types";

export interface ActionCardProps {
  block: ActionBlock;
  onApply: (block: ActionBlock) => void;
}

export const ActionCard: React.FC<ActionCardProps> = ({ block, onApply }) => {
  const [hasCopied, setHasCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(block.content);
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2000);
  };

  const targetLabel = ACTION_TARGET_LABELS[block.target] || block.target;
  const isCard = block.target === "story_card";
  const badgeTitle =
    isCard && block.metadata?.name
      ? `${block.metadata.type || "Card"}: ${block.metadata.name}`
      : targetLabel;

  return (
    <div className="my-3 border border-zinc-700 bg-zinc-900/90 rounded-none p-3 space-y-2 text-left shadow-lg">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
        <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 bg-amber-950/60 border border-amber-800/60 px-1.5 py-0.5">
          {badgeTitle}
        </span>
        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
          Suggested Action
        </span>
      </div>

      <pre className="font-mono text-xs text-zinc-200 whitespace-pre-wrap bg-zinc-950/70 p-2 border border-zinc-800/80 max-h-48 overflow-y-auto">
        {block.content}
      </pre>

      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={handleCopy}
          className="px-2.5 py-1 text-xs font-mono uppercase text-zinc-400 hover:text-zinc-100 bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-colors"
        >
          {hasCopied ? "Copied!" : "Copy"}
        </button>
        <button
          type="button"
          onClick={() => onApply(block)}
          className="px-3 py-1 text-xs font-semibold uppercase tracking-wider bg-zinc-100 text-zinc-950 hover:bg-white transition-colors border border-zinc-100"
        >
          {isCard ? "+ Add Card" : `Apply to ${targetLabel}`}
        </button>
      </div>
    </div>
  );
};
