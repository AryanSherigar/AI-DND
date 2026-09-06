import React from "react";
import { useAppSidebar } from "./appSidebarContext";

export interface SidebarSectionProps {
  label: string;
}

export const SidebarSection: React.FC<SidebarSectionProps> = ({ label }) => {
  const { collapsed } = useAppSidebar();

  if (collapsed) {
    return <div className="my-2 h-px w-5 self-center bg-border-subtle" />;
  }

  return (
    <p className="mb-1 mt-4 px-2.5 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-content-faint">
      {label}
    </p>
  );
};
