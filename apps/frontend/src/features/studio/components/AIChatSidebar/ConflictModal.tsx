import React from "react";
import { ConflictModalState } from "../../types/assistant.types";

export interface ConflictModalProps {
  state: ConflictModalState;
  onReplace: () => void;
  onAppend: () => void;
  onClose: () => void;
}

export const ConflictModal: React.FC<ConflictModalProps> = ({
  state,
  onReplace,
  onAppend,
  onClose,
}) => {
  if (!state.isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-surface-inset/80 backdrop-blur-xs p-4">
      <div className="rounded-md w-full max-w-lg bg-surface-inset border border-border-subtle p-6 space-y-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="border-b border-border-subtle pb-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
              Field Conflict Detected
            </span>
            <button
              type="button"
              onClick={onClose}
              className="text-content-faint hover:text-content-muted text-sm font-mono"
            >
              ✕
            </button>
          </div>
          <h3 className="text-lg font-semibold text-content mt-1">
            Update {state.targetLabel}
          </h3>
          <p className="text-xs text-content-muted mt-1">
            This field already contains text. Choose whether to replace it or
            append the AI suggestion to the end.
          </p>
        </div>

        <div className="space-y-4 text-xs font-mono">
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold text-content-muted uppercase tracking-wider">
              Current Text
            </label>
            <div className="rounded-md p-3 bg-surface border border-border-subtle text-content-muted max-h-32 overflow-y-auto whitespace-pre-wrap">
              {state.existingValue}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold text-accent uppercase tracking-wider">
              AI Proposed Text
            </label>
            <div className="rounded-md p-3 bg-surface border border-accent/20/40 text-content max-h-32 overflow-y-auto whitespace-pre-wrap">
              {state.newValue}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2 border-t border-border-subtle">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-content-muted hover:text-content transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onAppend}
            className="rounded-md px-4 py-2 text-xs font-semibold uppercase tracking-wider bg-surface-overlay hover:bg-surface text-content border border-border-subtle transition-colors"
          >
            Append to End
          </button>
          <button
            type="button"
            onClick={onReplace}
            className="px-4 py-2 text-xs font-semibold uppercase tracking-wider bg-content hover:bg-white text-surface font-bold transition-colors"
          >
            Replace Existing
          </button>
        </div>
      </div>
    </div>
  );
};
