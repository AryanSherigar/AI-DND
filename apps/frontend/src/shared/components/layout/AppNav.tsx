import React from "react";
import { useLocation } from "react-router-dom";
import {
  IconHome,
  IconCompass,
  IconPencilPlus,
  IconUser,
  IconHistory,
  IconBookmark,
} from "@tabler/icons-react";
import { SidebarRow } from "./SidebarRow";
import { SidebarDivider } from "./SidebarDivider";
import { useAuth } from "@/features/auth/hooks/useAuth";

export const AppNav: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();
  const isRoute = (path: string): boolean => location.pathname === path;

  return (
    <>
      <SidebarRow
        to="/"
        icon={<IconHome size={18} />}
        label="Home"
        isActive={isRoute("/")}
      />
      <SidebarRow
        to="/discover"
        icon={<IconCompass size={18} />}
        label="Discover"
        isActive={location.pathname.startsWith("/discover")}
      />
      <SidebarRow
        to="/studio"
        icon={<IconPencilPlus size={18} />}
        label="Studio"
        isActive={location.pathname.startsWith("/studio")}
      />
      <SidebarRow
        to={user ? "/profile" : "/login"}
        icon={<IconUser size={18} />}
        label={user ? "Profile" : "Sign in"}
        isActive={location.pathname.startsWith("/profile")}
      />

      {user && (
        <>
          <SidebarDivider />
          <SidebarRow
            to="/discover?played=true"
            icon={<IconHistory size={18} />}
            label="Played"
            isActive={location.search.includes("played=true")}
          />
          <SidebarRow
            to="/discover?saved=true"
            icon={<IconBookmark size={18} />}
            label="Saved"
            isActive={location.search.includes("saved=true")}
          />
        </>
      )}
    </>
  );
};
