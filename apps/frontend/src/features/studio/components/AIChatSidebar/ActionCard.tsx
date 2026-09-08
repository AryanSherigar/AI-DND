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
    <div className="my-3 border border-border-subtle bg-surface rounded-md p-3 space-y-2 text-left shadow-lg">
      <div className="flex items-center justify-between border-b border-border-subtle pb-1.5">
        <span className="rounded-md text-[10px] font-mono uppercase tracking-wider text-accent bg-accent/10 border border-accent/40 px-1.5 py-0.5">
          {badgeTitle}
        </span>
        <span className="text-[10px] font-mono uppercase tracking-wider text-content-faint">
          {isDelete ? "Proposed Deletion" : "Suggested Action"}
        </span>
      </div>

      {summary && (
        <p className="text-xs font-mono text-content-muted">{summary}</p>
      )}

      {validationErrors && validationErrors.length > 0 && (
        <div className="rounded-md border border-accent/40 bg-accent/10 p-2 text-[11px] text-accent space-y-0.5">
          <p className="font-semibold uppercase tracking-wider">
            Review before saving:
          </p>
          {validationErrors.map((error, idx) => (
            <p key={idx}>{error}</p>
          ))}
        </div>
      )}

      <pre className="rounded-md font-mono text-xs text-content whitespace-pre-wrap bg-surface-inset p-2 border border-border-subtle max-h-48 overflow-y-auto">
        {block.content}
      </pre>

      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={handleCopy}
          className="rounded-md px-2.5 py-1 text-xs font-mono uppercase text-content-muted hover:text-content bg-surface-inset border border-border-subtle hover:border-border-subtle transition-colors"
        >
          {hasCopied ? "Copied!" : "Copy"}
        </button>
        <button
          type="button"
          onClick={() => onApply(block)}
          disabled={isApplied}
          className="rounded-md px-3 py-1 text-xs font-semibold uppercase tracking-wider bg-content text-surface hover:bg-white transition-colors border border-content disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {applyLabel()}
        </button>
      </div>
    </div>
  );
};
