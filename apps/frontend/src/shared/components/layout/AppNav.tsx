import React from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import {
  IconHome,
  IconCompass,
  IconPencilPlus,
  IconUser,
  IconHistory,
  IconBookmark,
} from "@tabler/icons-react";
import { SidebarRow } from "./SidebarRow";
import { SidebarSection } from "./SidebarSection";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { GENRES } from "@/shared/constants/genres";
import { GENRE_COLORS } from "@/features/play/types/scenario";

const YOU_FILTER_KEYS = ["mine", "saved", "played"] as const;

const buildDiscoverHref = (
  params: URLSearchParams,
  updates: Record<string, string | null>,
): string => {
  const next = new URLSearchParams(params);
  for (const [key, value] of Object.entries(updates)) {
    if (value === null) next.delete(key);
    else next.set(key, value);
  }
  return `/discover?${next.toString()}`;
};

const buildYouHref = (
  params: URLSearchParams,
  key: (typeof YOU_FILTER_KEYS)[number],
): string => {
  const updates: Record<string, string | null> = { [key]: "true" };
  for (const other of YOU_FILTER_KEYS) {
    if (other !== key) updates[other] = null;
  }
  return buildDiscoverHref(params, updates);
};

const DiscoverSections: React.FC = () => {
  const [params] = useSearchParams();

  return (
    <>
      <SidebarSection label="You" />
      <SidebarRow
        to={buildYouHref(params, "played")}
        icon={<IconHistory size={18} />}
        label="Played"
        isActive={params.get("played") === "true"}
      />
      <SidebarRow
        to={buildYouHref(params, "saved")}
        icon={<IconBookmark size={18} />}
        label="Saved"
        isActive={params.get("saved") === "true"}
      />
      <SidebarRow
        to={buildYouHref(params, "mine")}
        icon={<IconPencilPlus size={18} />}
        label="Created"
        isActive={params.get("mine") === "true"}
      />

      <SidebarSection label="Genres" />
      {GENRES.map((genre) => (
        <SidebarRow
          key={genre}
          to={buildDiscoverHref(params, { genre })}
          isActive={params.getAll("genre").includes(genre)}
          icon={
            <span
              className="h-2 w-2 rounded-full"
              style={{
                backgroundColor:
                  GENRE_COLORS[genre as keyof typeof GENRE_COLORS] || "#6B7280",
              }}
            />
          }
          label={genre}
        />
      ))}
    </>
  );
};

export const AppNav: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();
  const isRoute = (path: string): boolean => location.pathname === path;
  const isDiscover = location.pathname.startsWith("/discover");
  const showBrowseSections =
    isDiscover || isRoute("/") || location.pathname.startsWith("/scenario");

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
        isActive={isDiscover}
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

      {showBrowseSections && <DiscoverSections />}
    </>
  );
};
