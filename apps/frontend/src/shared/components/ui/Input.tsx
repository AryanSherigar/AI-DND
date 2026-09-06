import React from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
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
        className={`w-full rounded-md border bg-surface-inset px-3 py-2 font-sans text-sm text-content placeholder:text-content-faint transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-50 ${
          hasError ? "border-danger" : "border-border-subtle"
        } ${className}`}
        aria-invalid={hasError}
        {...rest}
      />
      {hasError && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
};
