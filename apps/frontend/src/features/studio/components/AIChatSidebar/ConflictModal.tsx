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
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-xs p-4">
      <div className="w-full max-w-lg bg-zinc-950 border border-zinc-800 p-6 space-y-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="border-b border-zinc-800 pb-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-amber-400">
              Field Conflict Detected
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
            Update {state.targetLabel}
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            This field already contains text. Choose whether to replace it or
            append the AI suggestion to the end.
          </p>
        </div>

        <div className="space-y-4 text-xs font-mono">
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
              Current Text
            </label>
            <div className="p-3 bg-zinc-900 border border-zinc-800 text-zinc-400 max-h-32 overflow-y-auto whitespace-pre-wrap">
              {state.existingValue}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">
              AI Proposed Text
            </label>
            <div className="p-3 bg-zinc-900 border border-amber-900/40 text-zinc-200 max-h-32 overflow-y-auto whitespace-pre-wrap">
              {state.newValue}
            </div>
          </div>
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
            onClick={onAppend}
            className="px-4 py-2 text-xs font-semibold uppercase tracking-wider bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700 transition-colors"
          >
            Append to End
          </button>
          <button
            type="button"
            onClick={onReplace}
            className="px-4 py-2 text-xs font-semibold uppercase tracking-wider bg-zinc-100 hover:bg-white text-zinc-950 font-bold transition-colors"
          >
            Replace Existing
          </button>
        </div>
      </div>
    </div>
  );
};
