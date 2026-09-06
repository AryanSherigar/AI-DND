import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { IconSearch } from "@tabler/icons-react";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { cn } from "@/shared/lib/cn";
import { UserDropdown } from "./UserDropdown";

const LINKS = [
  { to: "/", label: "Home", exact: true },
  { to: "/discover", label: "Discover", exact: false },
  { to: "/studio", label: "Studio", exact: false },
];

const SPRING = { type: "spring", stiffness: 320, damping: 34 } as const;

export const FloatingNav: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [compact, setCompact] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handleScroll = (event: Event): void => {
      const target = event.target as HTMLElement | null;
      const top = target?.scrollTop ?? 0;
      // hysteresis so it doesn't flicker at the threshold
      setCompact((prev) => (prev ? top > 12 : top > 56));
    };
    window.addEventListener("scroll", handleScroll, true);
    return () => window.removeEventListener("scroll", handleScroll, true);
  }, []);

  const isActive = (to: string, exact: boolean): boolean =>
    exact ? location.pathname === to : location.pathname.startsWith(to);

  const handleSearchSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    const trimmed = query.trim();
    void navigate(
      trimmed ? `/discover?q=${encodeURIComponent(trimmed)}` : "/discover",
    );
  };

  return (
    <div className="pointer-events-none absolute inset-x-0 top-2.5 z-30 flex justify-center px-3">
      <motion.nav
        layout
        transition={SPRING}
        className="pointer-events-auto flex items-center gap-1 rounded-full border border-border-strong bg-surface/85 p-1.5 pl-4 shadow-elevated backdrop-blur-md"
      >
        <Link
          to="/"
          className="mr-1 shrink-0 font-mono text-sm font-semibold lowercase tracking-[0.25em] text-content transition-colors hover:text-accent"
        >
          wevr
        </Link>

        {LINKS.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={cn(
              "shrink-0 rounded-full px-3 py-1.5 font-sans text-sm transition-colors",
              isActive(link.to, link.exact)
                ? "bg-surface-overlay text-content"
                : "text-content-muted hover:text-content",
            )}
          >
            {link.label}
          </Link>
        ))}

        <AnimatePresence initial={false} mode="popLayout">
          {compact ? (
            <motion.button
              key="search-icon"
              layout
              type="button"
              onClick={() => navigate("/discover")}
              aria-label="Search scenarios"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={SPRING}
              className="ml-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border-subtle bg-surface-inset text-content-faint transition-colors hover:text-content"
            >
              <IconSearch size={15} />
            </motion.button>
          ) : (
            <motion.form
              key="search-input"
              layout
              onSubmit={handleSearchSubmit}
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              transition={SPRING}
              className="relative ml-1 flex items-center overflow-hidden"
            >
              <IconSearch
                size={15}
                className="pointer-events-none absolute left-2.5 text-content-faint"
              />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search"
                aria-label="Search scenarios"
                className="w-40 rounded-full border border-border-subtle bg-surface-inset py-1.5 pl-8 pr-3 font-sans text-sm text-content placeholder:text-content-faint focus-visible:border-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 lg:w-52"
              />
            </motion.form>
          )}
        </AnimatePresence>

        <span className="mx-1 h-4 w-px shrink-0 bg-border-strong" />

        {user ? (
          <UserDropdown user={user} onLogout={logout} />
        ) : (
          <Link
            to="/login"
            className="shrink-0 rounded-full bg-content px-4 py-1.5 font-sans text-sm font-medium text-surface transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Sign in
          </Link>
        )}
      </motion.nav>
    </div>
  );
};
