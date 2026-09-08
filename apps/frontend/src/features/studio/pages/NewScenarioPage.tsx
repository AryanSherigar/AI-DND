import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import { useStudioStore } from "../stores/studio.store";
import { StudioDocumentLayout } from "../components/Layout/StudioDocumentLayout";
import { MasterModeCreateFlow } from "../components/MasterModeCreateFlow/MasterModeCreateFlow";

const SaveStatusIndicator: React.FC<{
  isSaving: boolean;
  lastSaved: Date | null;
}> = ({ isSaving, lastSaved }) => {
  if (isSaving) {
    return (
      <span className="flex items-center gap-2 text-content-muted">
        <span className="h-3 w-3 animate-spin rounded-full border-b-2 border-content-muted" />
        Saving…
      </span>
    );
  }
  if (lastSaved) {
    return <span className="text-success">Saved</span>;
  }
  return <span className="text-content-faint">Unsaved draft</span>;
};

export const NewScenarioPage: React.FC = () => {
  const { mode, setMode, isSaving, lastSaved, resetDraft } = useStudioStore();

  // Reset store to fresh canvas on page mount
  useEffect(() => {
    resetDraft();
  }, [resetDraft]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-surface-sunken font-sans text-content">
      {/* Editor top bar — nav + mode toggle + save status */}
      <header className="z-50 flex flex-shrink-0 items-center justify-between gap-4 bg-surface-sunken px-5 py-2">
        <div className="flex items-center gap-5">
          <Link
            to="/"
            className="font-mono text-sm font-semibold lowercase tracking-[0.25em] text-content transition-colors hover:text-accent"
          >
            wevr
          </Link>
          <nav className="hidden items-center gap-1 lg:flex">
            <Link
              to="/"
              className="rounded-md px-2.5 py-1.5 font-sans text-sm text-content-muted transition-colors hover:text-content"
            >
              Home
            </Link>
            <Link
              to="/discover"
              className="rounded-md px-2.5 py-1.5 font-sans text-sm text-content-muted transition-colors hover:text-content"
            >
              Discover
            </Link>
            <Link
              to="/studio"
              className="rounded-md px-2.5 py-1.5 font-sans text-sm text-content transition-colors hover:text-content"
            >
              Studio
            </Link>
          </nav>
          <div className="flex gap-1 rounded-md border border-border-subtle bg-surface-raised p-1">
            <button
              onClick={() => setMode("newbie")}
              className={`rounded-sm px-4 py-1.5 text-xs uppercase tracking-wider transition-colors ${
                mode === "newbie"
                  ? "bg-content font-semibold text-surface"
                  : "text-content-faint hover:text-content-muted"
              }`}
            >
              Newbie
            </button>
            <button
              onClick={() => setMode("master")}
              className={`rounded-sm px-4 py-1.5 text-xs uppercase tracking-wider transition-colors ${
                mode === "master"
                  ? "bg-content font-semibold text-surface"
                  : "text-content-faint hover:text-content-muted"
              }`}
            >
              Master
            </button>
          </div>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider">
          <SaveStatusIndicator isSaving={isSaving} lastSaved={lastSaved} />
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
