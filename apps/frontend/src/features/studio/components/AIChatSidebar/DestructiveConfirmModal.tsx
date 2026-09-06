import React from "react";
import { DestructiveConfirmState } from "../../types/assistant.types";

export interface DestructiveConfirmModalProps {
  state: DestructiveConfirmState;
  onConfirm: () => void;
  onClose: () => void;
}

export const DestructiveConfirmModal: React.FC<
  DestructiveConfirmModalProps
> = ({ state, onConfirm, onClose }) => {
  if (!state.isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-surface-inset/80 backdrop-blur-xs p-4">
      <div className="rounded-md w-full max-w-lg bg-surface-inset border border-danger/40/60 p-6 space-y-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="border-b border-border-subtle pb-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-danger">
              Destructive Action
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
            Confirm Removal
          </h3>
          <p className="text-xs text-content-muted mt-2 whitespace-pre-wrap">
            {state.description}
          </p>
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
            onClick={onConfirm}
            className="rounded-md px-4 py-2 text-xs font-semibold uppercase tracking-wider bg-danger/10 hover:bg-danger/20 text-danger border border-danger/40 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};
