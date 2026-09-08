import React from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-accent-contrast border border-accent hover:bg-accent-strong hover:border-accent-strong disabled:bg-surface-overlay disabled:border-border-subtle disabled:text-content-faint",
  secondary:
    "bg-surface-raised text-content-muted border border-border-subtle hover:bg-surface-overlay hover:text-content disabled:bg-surface-raised disabled:text-content-faint",
  ghost:
    "bg-transparent text-content-muted border border-transparent hover:bg-surface-raised hover:text-content disabled:text-content-faint",
  danger:
    "bg-transparent text-danger border border-danger/50 hover:bg-danger/10 hover:border-danger disabled:text-content-faint disabled:border-border-subtle",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-xs rounded-sm",
  md: "px-4 py-2 text-sm rounded-md",
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
      className={`inline-flex items-center justify-center gap-2 font-sans font-medium transition duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface active:translate-y-px disabled:cursor-not-allowed disabled:active:translate-y-0 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
};
