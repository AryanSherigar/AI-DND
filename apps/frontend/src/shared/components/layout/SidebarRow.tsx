import React from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { cn } from "@/shared/lib/cn";
import { useAppSidebar } from "./appSidebarContext";

export interface SidebarRowProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  isActive?: boolean;
  onClick?: () => void;
}

export const SidebarRow: React.FC<SidebarRowProps> = ({
  to,
  icon,
  label,
  isActive = false,
  onClick,
}) => {
  const { collapsed } = useAppSidebar();

  return (
    <Link
      to={to}
      onClick={onClick}
      title={collapsed ? label : undefined}
      className={cn(
        "group/row relative flex items-center gap-3 rounded-lg py-2 font-sans text-sm transition-colors",
        collapsed ? "justify-center px-0" : "px-2.5",
        isActive
          ? "bg-surface-overlay text-content"
          : "text-content-muted hover:bg-surface-raised/70 hover:text-content",
      )}
    >
      {isActive && !collapsed && (
        <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
      )}
      <span className="flex h-5 w-5 shrink-0 items-center justify-center">
        {icon}
      </span>
      <motion.span
        animate={{
          opacity: collapsed ? 0 : 1,
          width: collapsed ? 0 : "auto",
        }}
        className="overflow-hidden whitespace-nowrap"
      >
        {label}
      </motion.span>
    </Link>
  );
};
