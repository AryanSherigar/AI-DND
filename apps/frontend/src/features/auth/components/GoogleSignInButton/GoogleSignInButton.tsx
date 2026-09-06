import React from "react";
import { Loader } from "@/shared/components/feedback/Loader";
import { GoogleSignInButtonProps } from "./GoogleSignInButton.types";

const GoogleGlyph: React.FC = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.76h3.57c2.08-1.92 3.27-4.74 3.27-8.09Z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.76c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.15-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
    />
    <path
      fill="#FBBC05"
      d="M5.85 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.67-2.84Z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.67 2.84C6.71 7.3 9.14 5.38 12 5.38Z"
    />
  </svg>
);

export const GoogleSignInButton: React.FC<GoogleSignInButtonProps> = ({
  onClick,
  isPending = false,
  disabled = false,
}) => {
  const handleClick = (): void => {
    if (isPending || disabled) return;
    onClick();
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || isPending}
      className="group inline-flex w-full items-center justify-center gap-3 rounded-lg border border-neutral-300 bg-white px-4 py-3 font-sans text-sm font-medium text-neutral-800 shadow-sm transition duration-150 hover:border-neutral-400 hover:bg-neutral-50 active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-800 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 disabled:active:translate-y-0"
    >
      {isPending ? <Loader size="sm" /> : <GoogleGlyph />}
      {isPending ? "Signing in…" : "Continue with Google"}
    </button>
  );
};
