import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { IconMenu2, IconX } from "@tabler/icons-react";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { cn } from "@/shared/lib/cn";
import {
  Navbar,
  NavBody,
  MobileNav,
  MobileNavHeader,
  MobileNavMenu,
} from "@/shared/components/ui/aceternity/resizable-navbar";
import { HeaderProps } from "./Header.types";
import { UserDropdown } from "./UserDropdown";

const NAV_LINKS = [
  { to: "/discover", label: "Discover" },
  { to: "/studio", label: "Studio" },
];

const Wordmark: React.FC = () => (
  <Link
    to="/"
    className="font-mono text-lg font-semibold lowercase tracking-[0.3em] text-content transition-colors hover:text-accent"
  >
    wevr
  </Link>
);

const DesktopLink: React.FC<{
  to: string;
  label: string;
  isActive: boolean;
}> = ({ to, label, isActive }) => (
  <Link
    to={to}
    className={cn(
      "rounded-md px-3 py-1.5 font-sans text-sm transition-colors",
      isActive ? "text-accent" : "text-content-muted hover:text-content",
    )}
  >
    {label}
  </Link>
);

export const Header: React.FC<HeaderProps> = ({ variant = "default" }) => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const isActive = (to: string): boolean => location.pathname.startsWith(to);

  const handleMobileToggle = (): void => setIsMobileOpen((prev) => !prev);
  const handleMobileClose = (): void => setIsMobileOpen(false);

  const handleMobileSignOut = (): void => {
    setIsMobileOpen(false);
    logout();
  };

  return (
    <Navbar
      className={cn("fixed top-0", variant === "landing" ? "pt-4" : "pt-3")}
    >
      <NavBody className="rounded-xl border border-border-subtle bg-surface/70 backdrop-blur-md">
        <Wordmark />
        <nav className="absolute inset-0 hidden items-center justify-center gap-1 lg:flex">
          {NAV_LINKS.map((link) => (
            <DesktopLink
              key={link.to}
              to={link.to}
              label={link.label}
              isActive={isActive(link.to)}
            />
          ))}
        </nav>
        <div className="relative z-10">
          {user ? (
            <UserDropdown user={user} onLogout={logout} />
          ) : (
            <Link
              to="/login"
              className="rounded-full border border-border-strong bg-surface-raised px-5 py-1.5 font-sans text-sm font-medium text-content transition hover:border-accent/60 hover:bg-surface-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Sign in
            </Link>
          )}
        </div>
      </NavBody>

      <MobileNav className="rounded-xl">
        <MobileNavHeader className="rounded-xl border border-border-subtle bg-surface/80 px-4 py-2 backdrop-blur-md">
          <Wordmark />
          <button
            onClick={handleMobileToggle}
            aria-label="Toggle navigation menu"
            className="text-content-muted"
          >
            {isMobileOpen ? <IconX size={20} /> : <IconMenu2 size={20} />}
          </button>
        </MobileNavHeader>
        <MobileNavMenu
          isOpen={isMobileOpen}
          onClose={handleMobileClose}
          className="rounded-xl border border-border-subtle bg-surface-overlay"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={handleMobileClose}
              className={cn(
                "w-full rounded-md px-3 py-2 font-sans text-sm",
                isActive(link.to)
                  ? "bg-surface-raised text-accent"
                  : "text-content-muted",
              )}
            >
              {link.label}
            </Link>
          ))}
          <div className="my-1 h-px w-full bg-border-subtle" />
          {user ? (
            <>
              <Link
                to="/profile"
                onClick={handleMobileClose}
                className="w-full px-3 py-1.5 font-sans text-sm text-content-muted"
              >
                Profile
              </Link>
              <button
                onClick={handleMobileSignOut}
                className="w-full px-3 py-1.5 text-left font-sans text-sm text-danger"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link
              to="/login"
              onClick={handleMobileClose}
              className="w-full rounded-md border border-border-strong bg-surface-raised px-3 py-2 text-center font-sans text-sm font-medium text-content"
            >
              Sign in
            </Link>
          )}
        </MobileNavMenu>
      </MobileNav>
    </Navbar>
  );
};
