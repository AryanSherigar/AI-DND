import React from "react";
import { Link, useLocation } from "react-router-dom";
import { GENRES } from "../../../shared/constants/genres";
import { GENRE_COLORS } from "../types/scenario";

const SidebarSection: React.FC<{ title?: string; children: React.ReactNode }> = ({
  title,
  children,
}) => (
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
}> = ({ to, icon, label }) => {
  const location = useLocation();
  const isActive = location.pathname === to || location.search.includes(to.split('?')[1] || "invalid");

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
        {icon && <span className="w-5 h-5 flex items-center justify-center">{icon}</span>}
        <span className="truncate">{label}</span>
      </Link>
    </li>
  );
};

export const DiscoverySidebar: React.FC = () => {
  return (
    <aside className="w-64 flex-shrink-0 h-full bg-[#0d0f14] border-r border-zinc-800 flex flex-col hidden md:flex overflow-y-auto custom-scrollbar">
      {/* Brand / Logo */}
      <div className="h-16 flex items-center px-6 border-b border-zinc-800/50 sticky top-0 bg-[#0d0f14] z-10">
        <Link to="/" className="font-fell-sc text-2xl text-white tracking-widest font-bold">
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
          <SidebarLink to="/discover?filter=history" label="Previous Scenarios" />
          <SidebarLink to="/discover?filter=saved" label="Saved Scenarios" />
          <SidebarLink to="/discover?filter=liked" label="Liked Scenarios" />
          <SidebarLink to="/discover?filter=created" label="Created Scenarios" />
        </SidebarSection>

        {/* Genres */}
        <SidebarSection title="Genres">
          {GENRES.map((genre) => (
            <SidebarLink
              key={genre}
              to={`/discover?genre=${genre.toLowerCase()}`}
              label={
                <span className="flex items-center gap-2">
                  <span 
                    className="w-2 h-2 rounded-full shadow-sm" 
                    style={{ backgroundColor: GENRE_COLORS[genre] || '#6B7280' }}
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
