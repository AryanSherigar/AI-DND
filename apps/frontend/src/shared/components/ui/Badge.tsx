import React from "react";

export type BadgeVariant = "default" | "success" | "warning" | "danger";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: "border-zinc-700 bg-zinc-900 text-zinc-300",
  success: "border-emerald-800 bg-emerald-950 text-emerald-300",
  warning: "border-amber-800 bg-amber-950 text-amber-300",
  danger: "border-red-800 bg-red-950 text-red-300",
};

export const Badge: React.FC<BadgeProps> = ({
  variant = "default",
  className = "",
  children,
  ...rest
}) => {
  return (
    <span
      className={`inline-flex items-center rounded-none border px-2 py-0.5 font-sans text-xs font-medium tracking-wide ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
};
