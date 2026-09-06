import React, { useState } from "react";
import {
  ActionBlock,
  ACTION_TARGET_LABELS,
  isDeleteActionBlock,
  MASTER_EXPRESSION_TARGETS,
  MASTER_STRUCTURED_TARGETS,
} from "../../types/assistant.types";

export interface ActionCardProps {
  block: ActionBlock;
  onApply: (block: ActionBlock) => void;
  isApplied?: boolean;
  validationErrors?: string[];
}

const describeStructuredBlock = (block: ActionBlock): string | null => {
  try {
    const parsed = JSON.parse(block.content) as Record<string, unknown>;
    if (block.target === "entity") {
      return `Entity: ${parsed.canonical_name} (${parsed.entity_type})`;
    }
    if (block.target === "fact") {
      const object =
        parsed.object_literal ?? parsed.object_ref ?? parsed.object_entity_id;
      return `Fact: ${parsed.subject_ref ?? parsed.subject_entity_id} → ${parsed.predicate} → ${object}`;
    }
    if (block.target === "state_field") {
      const key = parsed.key ?? block.metadata?.key;
      return `Tracked Value: ${key} (${parsed.type})`;
    }
    if (block.target === "condition") {
      return `Active Rule: ${parsed.label}`;
    }
    if (block.target === "invariant") {
      return `Always-True Rule: ${parsed.label}`;
    }
    if (block.target === "end_condition") {
      return `${parsed.outcome_tag === "win" ? "Win" : "Lose"} Condition: ${parsed.outcome_title}`;
    }
    return null;
  } catch {
    return null;
  }
};

export const ActionCard: React.FC<ActionCardProps> = ({
  block,
  onApply,
  isApplied = false,
  validationErrors,
}) => {
  const [hasCopied, setHasCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(block.content);
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2000);
  };

  const targetLabel = ACTION_TARGET_LABELS[block.target] || block.target;
  const isCard = block.target === "story_card";
  const isDelete = isDeleteActionBlock(block);
  const isStructured = MASTER_STRUCTURED_TARGETS.includes(block.target);
  const isExpressionTarget = MASTER_EXPRESSION_TARGETS.includes(block.target);
  const summary =
    isStructured || isExpressionTarget ? describeStructuredBlock(block) : null;
  const badgeTitle =
    isCard && block.metadata?.name
      ? `${block.metadata.type || "Card"}: ${block.metadata.name}`
      : targetLabel;

  const applyLabel = () => {
    if (isApplied) return "Applied";
    if (isDelete) return `Delete ${targetLabel}`;
    if (isCard) return "+ Add Card";
    if (isExpressionTarget) return `Review ${targetLabel}`;
    if (isStructured) return `+ Add ${targetLabel}`;
    return `Apply to ${targetLabel}`;
  };

  return (
    <div className="my-3 border border-zinc-700 bg-zinc-900/90 rounded-none p-3 space-y-2 text-left shadow-lg">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
        <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 bg-amber-950/60 border border-amber-800/60 px-1.5 py-0.5">
          {badgeTitle}
        </span>
        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
          {isDelete ? "Proposed Deletion" : "Suggested Action"}
        </span>
      </div>

      {summary && <p className="text-xs font-mono text-zinc-300">{summary}</p>}

      {validationErrors && validationErrors.length > 0 && (
        <div className="border border-amber-800/60 bg-amber-950/40 p-2 text-[11px] text-amber-300 space-y-0.5">
          <p className="font-semibold uppercase tracking-wider">
            Review before saving:
          </p>
          {validationErrors.map((error, idx) => (
            <p key={idx}>{error}</p>
          ))}
        </div>
      )}

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
          disabled={isApplied}
          className="px-3 py-1 text-xs font-semibold uppercase tracking-wider bg-zinc-100 text-zinc-950 hover:bg-white transition-colors border border-zinc-100 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {applyLabel()}
        </button>
      </div>
    </div>
  );
};
