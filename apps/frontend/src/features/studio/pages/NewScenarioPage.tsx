import React, { useEffect } from "react";
import { useStudioStore } from "../stores/studio.store";
import { StudioDocumentLayout } from "../components/Layout/StudioDocumentLayout";
import { MasterModeCreateFlow } from "../components/MasterModeCreateFlow/MasterModeCreateFlow";

export const NewScenarioPage: React.FC = () => {
  const { mode, setMode, isSaving, lastSaved, resetDraft } = useStudioStore();

  // Reset store to fresh canvas on page mount
  useEffect(() => {
    resetDraft();
  }, [resetDraft]);

  return (
    <div className="h-screen overflow-hidden bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* Top Navigation / Mode Toggle */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950 flex-shrink-0 z-50">
        <div className="flex items-center gap-6">
          <h1 className="text-sm font-semibold text-zinc-100 tracking-widest uppercase font-mono">
            AI-DND Studio
          </h1>
          <div className="flex bg-zinc-900 p-1 border border-zinc-800">
            <button
              onClick={() => setMode("newbie")}
              className={`px-4 py-1.5 text-xs uppercase tracking-wider transition-all rounded-none ${
                mode === "newbie"
                  ? "bg-zinc-100 text-zinc-950 font-semibold"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Newbie Mode
            </button>
            <button
              onClick={() => setMode("master")}
              className={`px-4 py-1.5 text-xs uppercase tracking-wider transition-all rounded-none ${
                mode === "master"
                  ? "bg-zinc-100 text-zinc-950 font-semibold"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Master Mode
            </button>
          </div>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider">
          {isSaving ? (
            <span className="flex items-center gap-2 text-zinc-400 font-mono">
              <span className="animate-spin rounded-full h-3 w-3 border-b-2 border-zinc-400"></span>
              Saving...
            </span>
          ) : lastSaved ? (
            <span className="flex items-center gap-1 text-emerald-400 font-mono">
              Saved
            </span>
          ) : (
            <span className="text-zinc-500 font-mono">Unsaved Draft</span>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative min-h-0">
        {mode === "newbie" ? (
          <StudioDocumentLayout />
        ) : (
          <MasterModeCreateFlow />
        )}
      </main>
    </div>
  );
};
