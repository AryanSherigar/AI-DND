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
        "group/row flex items-center gap-3 rounded-md px-1 py-2 font-sans text-sm transition-colors",
        isActive ? "text-content" : "text-content-muted hover:text-content",
      )}
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center">
        {icon}
      </span>
      <motion.span
        animate={{
          opacity: collapsed ? 0 : 1,
          width: collapsed ? 0 : "auto",
        }}
        className="overflow-hidden whitespace-nowrap transition-transform duration-150 group-hover/row:translate-x-0.5"
      >
        {label}
      </motion.span>
    </Link>
  );
};
