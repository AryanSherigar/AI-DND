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
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-xs p-4">
      <div className="w-full max-w-lg bg-zinc-950 border border-red-900/60 p-6 space-y-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="border-b border-zinc-800 pb-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-red-400">
              Destructive Action
            </span>
            <button
              type="button"
              onClick={onClose}
              className="text-zinc-500 hover:text-zinc-300 text-sm font-mono"
            >
              ✕
            </button>
          </div>
          <h3 className="text-lg font-semibold text-zinc-100 mt-1">
            Confirm Removal
          </h3>
          <p className="text-xs text-zinc-400 mt-2 whitespace-pre-wrap">
            {state.description}
          </p>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2 border-t border-zinc-900">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-4 py-2 text-xs font-semibold uppercase tracking-wider bg-red-950 hover:bg-red-900 text-red-200 border border-red-800 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};
