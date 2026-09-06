import React from "react";
import { motion } from "motion/react";
import { cn } from "@/shared/lib/cn";

export type LoaderVariant = "ring" | "dots";
export type LoaderSize = "sm" | "md" | "lg";

export interface LoaderProps {
  variant?: LoaderVariant;
  size?: LoaderSize;
  label?: string;
  className?: string;
}

const RING_SIZE: Record<LoaderSize, string> = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-9 w-9 border-[3px]",
};

const DOT_SIZE: Record<LoaderSize, string> = {
  sm: "h-1.5 w-1.5",
  md: "h-2 w-2",
  lg: "h-2.5 w-2.5",
};

const Ring: React.FC<{ size: LoaderSize }> = ({ size }) => (
  <span
    className={cn(
      "inline-block animate-spin rounded-full border-border-strong border-t-accent",
      RING_SIZE[size],
    )}
  />
);

const Dots: React.FC<{ size: LoaderSize }> = ({ size }) => (
  <span className="inline-flex items-center gap-1.5">
    {[0, 1, 2].map((index) => (
      <motion.span
        key={index}
        className={cn("rounded-full bg-accent", DOT_SIZE[size])}
        animate={{ opacity: [0.25, 1, 0.25], y: [0, -3, 0] }}
        transition={{
          duration: 0.9,
          repeat: Infinity,
          ease: "easeInOut",
          delay: index * 0.15,
        }}
      />
    ))}
  </span>
);

export const Loader: React.FC<LoaderProps> = ({
  variant = "ring",
  size = "md",
  label,
  className = "",
}) => {
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn("inline-flex items-center gap-3", className)}
    >
      {variant === "ring" ? <Ring size={size} /> : <Dots size={size} />}
      {label ? (
        <span className="font-mono text-xs uppercase tracking-wider text-content-faint">
          {label}
        </span>
      ) : (
        <span className="sr-only">Loading</span>
      )}
    </span>
  );
};
