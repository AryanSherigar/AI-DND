import React from "react";
import { Link } from "react-router-dom";

export interface LegalPageProps {
  title: string;
  children: React.ReactNode;
}

export const LegalPage: React.FC<LegalPageProps> = ({ title, children }) => {
  return (
    <main className="mx-auto min-h-screen max-w-2xl bg-surface px-6 py-20 text-content">
      <Link
        to="/"
        className="font-mono text-sm font-semibold lowercase tracking-[0.3em] text-content-muted transition-colors hover:text-content"
      >
        wevr
      </Link>
      <h1 className="mt-8 font-display text-3xl text-content">{title}</h1>
      <div className="mt-6 space-y-4 font-sans text-sm leading-relaxed text-content-muted">
        {children}
      </div>
    </main>
  );
};
