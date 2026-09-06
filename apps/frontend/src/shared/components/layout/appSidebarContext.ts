import { createContext, useContext } from "react";

export interface AppSidebarContextValue {
  collapsed: boolean;
  mobileOpen: boolean;
}

export const AppSidebarContext = createContext<AppSidebarContextValue>({
  collapsed: false,
  mobileOpen: false,
});

export const useAppSidebar = (): AppSidebarContextValue =>
  useContext(AppSidebarContext);
