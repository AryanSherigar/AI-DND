import React from "react";
import { Link, useLocation } from "react-router-dom";
import { MobileNavProps } from "./Header.types";

export const MobileNav: React.FC<MobileNavProps> = ({
  isOpen,
  onClose,
  user,
  onLogout,
}) => {
  const location = useLocation();

  if (!isOpen) {
    return null;
  }

  const handleSignOut = () => {
    onClose();
    onLogout();
  };

  const is_discover_active = location.pathname.startsWith("/discover");
  const is_studio_active = location.pathname.startsWith("/studio");

  return (
    <div className="md:hidden border-b border-zinc-800 bg-[#0d0f14]/98 backdrop-blur-xl px-6 py-5 shadow-2xl space-y-4 font-mono">
      <nav className="flex flex-col space-y-3">
        <Link
          to="/discover"
          onClick={onClose}
          className={`px-3 py-2 rounded-lg text-sm transition-colors ${
            is_discover_active
              ? "bg-zinc-800 text-amber-300 font-bold"
              : "text-zinc-300 hover:text-white hover:bg-zinc-800/50"
          }`}
        >
          Discover
        </Link>
        <Link
          to="/studio"
          onClick={onClose}
          className={`px-3 py-2 rounded-lg text-sm transition-colors ${
            is_studio_active
              ? "bg-zinc-800 text-amber-300 font-bold"
              : "text-zinc-300 hover:text-white hover:bg-zinc-800/50"
          }`}
        >
          Studio
        </Link>
      </nav>

      <div className="border-t border-zinc-800/80 pt-3">
        {user ? (
          <div className="space-y-2">
            <div className="px-3 text-xs text-amber-400/80 flex items-center gap-1.5">
              <span>✦</span>
              <span className="font-bold truncate">
                {user.display_name || "Adventurer"}
              </span>
            </div>
            <Link
              to="/profile"
              onClick={onClose}
              className="block px-3 py-1.5 text-xs text-zinc-300 hover:text-amber-300"
            >
              📜 Adventurer Profile
            </Link>
            <Link
              to="/profile?tab=creations"
              onClick={onClose}
              className="block px-3 py-1.5 text-xs text-zinc-300 hover:text-amber-300"
            >
              ⚔️ My Creations
            </Link>
            <Link
              to="/profile?tab=bookmarks"
              onClick={onClose}
              className="block px-3 py-1.5 text-xs text-zinc-300 hover:text-amber-300"
            >
              ⭐ Bookmarks
            </Link>
            <button
              onClick={handleSignOut}
              className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:text-red-300"
            >
              🚪 Sign Out
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            onClick={onClose}
            className="block text-center w-full py-2.5 rounded-md bg-white/10 hover:bg-white/20 border border-white/20 text-white font-medium text-sm transition-all shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)]"
          >
            Sign In
          </Link>
        )}
      </div>
    </div>
  );
};
