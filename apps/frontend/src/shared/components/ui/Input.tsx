import React from "react";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input: React.FC<InputProps> = ({
  error,
  className = "",
  id,
  ...rest
}) => {
  const hasError = Boolean(error);

  return (
    <div className="w-full">
      <input
        id={id}
        className={`w-full rounded-none border bg-zinc-900 px-3 py-2 font-sans text-sm text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-50 ${
          hasError ? "border-red-800" : "border-zinc-800"
        } ${className}`}
        aria-invalid={hasError}
        {...rest}
      />
      {hasError && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
};
