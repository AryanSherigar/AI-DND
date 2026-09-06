import React from "react";
import { Link } from "react-router-dom";

export const NotFoundPage: React.FC = () => {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-5 bg-surface px-6 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent">
        404
      </p>
      <h1 className="font-fell-sc text-3xl text-content">
        This path leads nowhere
      </h1>
      <p className="max-w-sm font-sans text-sm text-content-faint">
        The page you were looking for has wandered off, or never existed.
      </p>
      <Link
        to="/"
        className="rounded-md border border-border-subtle bg-surface-raised px-4 py-2 font-sans text-sm text-content-muted transition hover:bg-surface-overlay hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
      >
        Back to wevr
      </Link>
    </main>
  );
};
