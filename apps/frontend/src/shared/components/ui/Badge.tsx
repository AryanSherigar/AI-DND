import React from "react";

export type BadgeVariant = "default" | "success" | "warning" | "danger";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: "border-border-subtle bg-surface-raised text-content-muted",
  success: "border-success/40 bg-success/10 text-success",
  warning: "border-warning/40 bg-warning/10 text-warning",
  danger: "border-danger/40 bg-danger/10 text-danger",
};

export const Badge: React.FC<BadgeProps> = ({
  variant = "default",
  className = "",
  children,
  ...rest
}) => {
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-2 py-0.5 font-sans text-xs font-medium tracking-wide ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
};
