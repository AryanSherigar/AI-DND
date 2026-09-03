import React from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-zinc-100 text-zinc-950 border border-zinc-100 hover:bg-white disabled:bg-zinc-700 disabled:border-zinc-700 disabled:text-zinc-400",
  secondary:
    "bg-zinc-900 text-zinc-300 border border-zinc-800 hover:bg-zinc-800 hover:text-zinc-100 disabled:bg-zinc-900 disabled:text-zinc-600",
  ghost:
    "bg-transparent text-zinc-300 border border-transparent hover:bg-zinc-900 hover:text-zinc-100 disabled:text-zinc-600",
  danger:
    "bg-red-950 text-red-300 border border-red-900 hover:bg-red-900 hover:text-red-100 disabled:bg-red-950 disabled:text-red-700",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  size = "md",
  disabled = false,
  className = "",
  children,
  ...rest
}) => {
  return (
    <button
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-none font-sans font-medium transition-colors focus:outline-none focus:border-zinc-400 disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
};
