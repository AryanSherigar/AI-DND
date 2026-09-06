import React from "react";
import { cn } from "@/shared/lib/cn";
import { useAppSidebar } from "./appSidebarContext";

export const SidebarDivider: React.FC = () => {
  const { collapsed } = useAppSidebar();
  return (
    <div
      className={cn(
        "my-3 h-px bg-border-subtle transition-all",
        collapsed ? "w-5" : "w-full",
      )}
    />
  );
};
