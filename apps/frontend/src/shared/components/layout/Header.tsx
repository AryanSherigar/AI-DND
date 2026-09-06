import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { HeaderProps } from "./Header.types";
import { UserDropdown } from "./UserDropdown";
import { MobileNav } from "./MobileNav";

const getHeaderContainerClass = (
  is_landing: boolean,
  is_scrolled: boolean,
): string => {
  const base = "fixed top-0 left-0 right-0 z-50 transition-all duration-300";
  if (is_landing) {
    if (is_scrolled) {
      return `${base} bg-[#0d0f14]/90 backdrop-blur-md border-b border-zinc-800/80 shadow-lg shadow-black/50 py-4`;
    }
    return `${base} bg-transparent py-6 md:py-8`;
  }
  return `${base} bg-white/5 backdrop-blur-lg border-b border-white/20 shadow-[inset_0_1px_1px_rgba(255,255,255,0.4),0_4px_20px_rgba(0,0,0,0.5)] py-4`;
};

const getNavLinkClass = (is_active: boolean): string => {
  if (is_active) {
    return "text-amber-300 font-bold drop-shadow-[0_0_8px_rgba(212,175,106,0.5)] transition-colors";
  }
  return "text-white/80 hover:text-white transition-colors hover:drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]";
};

export const Header: React.FC<HeaderProps> = ({ variant = "default" }) => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [is_scrolled, setIsScrolled] = useState(false);
  const [is_mobile_menu_open, setIsMobileMenuOpen] = useState(false);

  const is_landing = variant === "landing";
  const is_discover_active = location.pathname.startsWith("/discover");
  const is_studio_active = location.pathname.startsWith("/studio");

  useEffect(() => {
    if (!is_landing) return;

    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [is_landing]);

  const handleLogoClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (location.pathname === "/") {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const handleMobileMenuToggle = () => {
    setIsMobileMenuOpen((prev) => !prev);
  };

  return (
    <header className={getHeaderContainerClass(is_landing, is_scrolled)}>
      <div className="px-6 md:px-12 flex items-center justify-between w-full max-w-7xl mx-auto">
        {/* Left: Brand Logo */}
        <Link
          to="/"
          onClick={handleLogoClick}
          className="flex items-center gap-2 group"
          title="Return to Realm Gateway"
        >
          <span className="font-fell-sc text-white text-2xl md:text-3xl font-bold tracking-widest drop-shadow-md group-hover:text-amber-200 transition-colors">
            AI-DND
          </span>
        </Link>

        {/* Center: Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-8 font-mono text-sm tracking-wider">
          <Link
            to="/discover"
            className={getNavLinkClass(is_discover_active)}
          >
            Discover
          </Link>
          <Link to="/studio" className={getNavLinkClass(is_studio_active)}>
            Studio
          </Link>
        </nav>

        {/* Right: Auth Actions & Mobile Menu Toggle */}
        <div className="flex items-center gap-3 font-mono">
          <div className="hidden md:block">
            {user ? (
              <UserDropdown user={user} onLogout={logout} />
            ) : (
              <Link
                to="/login"
                className="px-5 py-2 rounded-md bg-white/10 hover:bg-white/20 border border-white/20 hover:border-amber-400/50 hover:shadow-[0_0_12px_rgba(212,175,106,0.3)] shadow-[inset_0_1px_1px_rgba(255,255,255,0.3)] transition-all text-white font-medium text-sm"
              >
                Sign In
              </Link>
            )}
          </div>

          <button
            onClick={handleMobileMenuToggle}
            className="md:hidden p-2 rounded-lg border border-zinc-800 bg-zinc-900/80 text-zinc-300 hover:text-white transition-colors"
            aria-label="Toggle navigation menu"
          >
            <span className="text-lg leading-none">
              {is_mobile_menu_open ? "✕" : "☰"}
            </span>
          </button>
        </div>
      </div>

      <MobileNav
        isOpen={is_mobile_menu_open}
        onClose={() => setIsMobileMenuOpen(false)}
        user={user}
        onLogout={logout}
      />
    </header>
  );
};
