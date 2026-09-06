import React from "react";

export const ErrorFallback: React.FC = () => {
  const handleReload = (): void => {
    window.location.reload();
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-surface px-6 text-center">
      <p className="font-display text-2xl text-content">Something broke</p>
      <p className="max-w-sm font-mono text-sm text-content-faint">
        The page hit an unexpected error. Reloading usually clears it.
      </p>
      <button
        onClick={handleReload}
        className="rounded-md border border-border-subtle bg-surface-raised px-4 py-2 font-sans text-sm text-content-muted transition hover:bg-surface-overlay hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        Reload
      </button>
    </div>
  );
};
