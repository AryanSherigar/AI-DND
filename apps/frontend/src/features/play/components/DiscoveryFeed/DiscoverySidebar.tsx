import React from "react";
import { Link, useLocation } from "react-router-dom";
import { GENRES } from "../../../../shared/constants/genres";
import { GENRE_COLORS } from "../../types/scenario";

interface DiscoverySidebarProps {
  searchParams: URLSearchParams;
}

const YOU_FILTER_KEYS = ["mine", "saved", "played"] as const;

const buildDiscoverHref = (
  searchParams: URLSearchParams,
  updates: Record<string, string | null>,
): string => {
  const newParams = new URLSearchParams(searchParams);
  for (const [key, value] of Object.entries(updates)) {
    if (value === null) {
      newParams.delete(key);
    } else {
      newParams.set(key, value);
    }
  }
  return `/discover?${newParams.toString()}`;
};

const buildYouFilterHref = (
  searchParams: URLSearchParams,
  key: (typeof YOU_FILTER_KEYS)[number],
): string => {
  const updates: Record<string, string | null> = { [key]: "true" };
  for (const otherKey of YOU_FILTER_KEYS) {
    if (otherKey !== key) updates[otherKey] = null;
  }
  return buildDiscoverHref(searchParams, updates);
};

const SidebarSection: React.FC<{
  title?: string;
  children: React.ReactNode;
}> = ({ title, children }) => (
  <div className="py-4 border-b border-zinc-800/50 last:border-b-0">
    {title && (
      <h3 className="px-6 mb-2 text-sm font-semibold text-zinc-500 uppercase tracking-wider font-mono">
        {title}
      </h3>
    )}
    <ul className="space-y-1">{children}</ul>
  </div>
);

const SidebarLink: React.FC<{
  to: string;
  icon?: React.ReactNode;
  label: React.ReactNode;
  isActive?: boolean;
}> = ({ to, icon, label, isActive: isActiveProp }) => {
  const location = useLocation();
  const isActive =
    isActiveProp ??
    (location.pathname === to ||
      location.search.includes(to.split("?")[1] || "invalid"));

  return (
    <li>
      <Link
        to={to}
        className={`flex items-center gap-4 px-6 py-2.5 mx-2 rounded-lg transition-colors font-mono text-sm ${
          isActive
            ? "bg-zinc-800 text-white font-medium"
            : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
        }`}
      >
        {icon && (
          <span className="w-5 h-5 flex items-center justify-center">
            {icon}
          </span>
        )}
        <span className="truncate">{label}</span>
      </Link>
    </li>
  );
};

export const DiscoverySidebar: React.FC<DiscoverySidebarProps> = ({
  searchParams,
}) => {
  return (
    <aside className="w-64 flex-shrink-0 h-full bg-[#0d0f14] border-r border-zinc-800 flex flex-col hidden md:flex overflow-y-auto custom-scrollbar">
      {/* Brand / Logo */}
      <div className="h-16 flex items-center px-6 border-b border-zinc-800/50 sticky top-0 bg-[#0d0f14] z-10">
        <Link
          to="/"
          className="font-fell-sc text-2xl text-white tracking-widest font-bold"
        >
          AI-DND
        </Link>
      </div>

      <nav className="flex-1 py-2">
        {/* Main Links */}
        <SidebarSection>
          <SidebarLink to="/" label="Home" />
          <SidebarLink to="/" label="Profile" />
          <SidebarLink to="/studio" label="Create Scenario" />
        </SidebarSection>

        {/* You Section */}
        <SidebarSection title="You">
          <SidebarLink
            to={buildYouFilterHref(searchParams, "played")}
            label="Previous Scenarios"
            isActive={searchParams.get("played") === "true"}
          />
          <SidebarLink
            to={buildYouFilterHref(searchParams, "saved")}
            label="Saved Scenarios"
            isActive={searchParams.get("saved") === "true"}
          />
          <SidebarLink
            to={buildYouFilterHref(searchParams, "mine")}
            label="Created Scenarios"
            isActive={searchParams.get("mine") === "true"}
          />
        </SidebarSection>

        {/* Genres */}
        <SidebarSection title="Genres">
          {GENRES.map((genre) => (
            <SidebarLink
              key={genre}
              to={buildDiscoverHref(searchParams, { genre })}
              isActive={searchParams.getAll("genre").includes(genre)}
              label={
                <span className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full shadow-sm"
                    style={{
                      backgroundColor:
                        GENRE_COLORS[genre as keyof typeof GENRE_COLORS] ||
                        "#6B7280",
                    }}
                  />
                  {genre}
                </span>
              }
            />
          ))}
        </SidebarSection>
      </nav>
    </aside>
  );
};
