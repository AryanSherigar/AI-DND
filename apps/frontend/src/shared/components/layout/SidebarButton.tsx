import React from "react";
import { motion } from "motion/react";
import { cn } from "@/shared/lib/cn";
import { useAppSidebar } from "./appSidebarContext";

export interface SidebarButtonProps {
  icon: React.ReactNode;
  label: string;
  isActive?: boolean;
  onClick: () => void;
}

export const SidebarButton: React.FC<SidebarButtonProps> = ({
  icon,
  label,
  isActive = false,
  onClick,
}) => {
  const { collapsed } = useAppSidebar();

  return (
    <button
      type="button"
      onClick={onClick}
      title={collapsed ? label : undefined}
      className={cn(
        "group/row relative flex w-full items-center gap-3 rounded-lg py-2 text-left font-sans text-sm transition-colors",
        collapsed ? "justify-center px-0" : "px-2.5",
        isActive
          ? "bg-surface-overlay text-content"
          : "text-content-muted hover:bg-surface-raised/70 hover:text-content",
      )}
    >
      {isActive && !collapsed && (
        <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
      )}
      <span
        className={cn(
          "flex h-5 w-5 shrink-0 items-center justify-center",
          isActive && "text-accent",
        )}
      >
        {icon}
      </span>
      <motion.span
        animate={{ opacity: collapsed ? 0 : 1, width: collapsed ? 0 : "auto" }}
        className="overflow-hidden whitespace-nowrap"
      >
        {label}
      </motion.span>
    </button>
  );
};
