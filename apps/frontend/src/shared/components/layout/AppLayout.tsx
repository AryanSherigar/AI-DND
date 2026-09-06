import React from "react";
import { Outlet } from "react-router-dom";
import { AppShell } from "./AppShell";
import { AppNav } from "./AppNav";

export const AppLayout: React.FC = () => {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-surface-sunken text-content">
      <AppShell nav={<AppNav />}>
        <Outlet />
      </AppShell>
    </div>
  );
};
