import React, { useState } from "react";
import { IconSparkles, IconCopy, IconCheck } from "@tabler/icons-react";
import { Loader } from "@/shared/components/feedback/Loader";
import { JudgeSignInButtonProps } from "./JudgeSignInButton.types";
import {
  DEFAULT_JUDGE_EMAIL,
  DEFAULT_JUDGE_PASSWORD,
} from "../../constants/auth.constants";

export const JudgeSignInButton: React.FC<JudgeSignInButtonProps> = ({
  onClick,
  isPending = false,
  disabled = false,
  judgeEmail = DEFAULT_JUDGE_EMAIL,
  judgePassword = DEFAULT_JUDGE_PASSWORD,
}) => {
  const [hasCopied, setHasCopied] = useState(false);

  const handleClick = (): void => {
    if (isPending || disabled) return;
    onClick();
  };

  const handleCopyCredentials = async (
    e: React.MouseEvent<HTMLButtonElement>,
  ): Promise<void> => {
    e.stopPropagation();
    await navigator.clipboard.writeText(
      `Email: ${judgeEmail}\nPassword: ${judgePassword}`,
    );
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2000);
  };

  return (
    <div className="flex flex-col gap-2.5">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || isPending}
        className="group inline-flex w-full items-center justify-center gap-2.5 rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3 font-sans text-sm font-medium text-white shadow-sm transition duration-150 hover:bg-neutral-800 active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 disabled:active:translate-y-0"
      >
        {isPending ? (
          <Loader size="sm" />
        ) : (
          <IconSparkles className="h-4 w-4 text-amber-300" aria-hidden="true" />
        )}
        <span>{isPending ? "Entering as Judge…" : "Quick Login as Judge"}</span>
      </button>

      <div className="flex items-center justify-between rounded-md border border-neutral-200 bg-white/80 px-3 py-2 text-xs text-neutral-600 backdrop-blur-sm">
        <div className="flex flex-col gap-0.5 truncate pr-2">
          <span className="font-mono text-[11px] tracking-wider text-neutral-400 uppercase">
            Demo Credentials
          </span>
          <span className="truncate font-mono text-neutral-700">
            {judgeEmail}
          </span>
        </div>
        <button
          type="button"
          onClick={handleCopyCredentials}
          className="inline-flex shrink-0 items-center gap-1 rounded border border-neutral-200 bg-neutral-50 px-2 py-1 font-mono text-[11px] text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-neutral-400"
          title="Copy judge credentials"
        >
          {hasCopied ? (
            <IconCheck className="h-3.5 w-3.5 text-emerald-600" />
          ) : (
            <IconCopy className="h-3.5 w-3.5" />
          )}
          <span>{hasCopied ? "Copied" : "Copy"}</span>
        </button>
      </div>
    </div>
  );
};
