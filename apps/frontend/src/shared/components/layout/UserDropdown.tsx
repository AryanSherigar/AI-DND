import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { UserDropdownProps } from "./Header.types";

export const UserDropdown: React.FC<UserDropdownProps> = ({
  user,
  onLogout,
}) => {
  const [is_open, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const handleToggle = () => {
    setIsOpen((prev) => !prev);
  };

  const handleSignOut = () => {
    setIsOpen(false);
    onLogout();
  };

  const handleClose = () => {
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={handleToggle}
        aria-expanded={is_open}
        aria-haspopup="true"
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-900/80 hover:bg-zinc-800/80 border border-zinc-700/60 shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)] text-white text-sm font-mono transition-all group"
      >
        <span className="text-amber-400 text-xs">✦</span>
        <span className="font-semibold text-zinc-200 group-hover:text-amber-300 transition-colors max-w-[140px] truncate">
          {user.display_name || "Adventurer"}
        </span>
        <span className="text-zinc-500 text-xs transition-transform duration-200 group-hover:text-zinc-300">
          ▼
        </span>
      </button>

      {is_open && (
        <div className="absolute right-0 mt-2 w-48 rounded-lg bg-[#0d0f14]/95 border border-zinc-800 shadow-2xl backdrop-blur-xl py-1 z-50 font-mono text-xs text-zinc-300">
          <Link
            to="/profile"
            onClick={handleClose}
            className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800/60 hover:text-amber-300 transition-colors"
          >
            <span>📜</span>
            <span>Adventurer Profile</span>
          </Link>
          <Link
            to="/profile?tab=creations"
            onClick={handleClose}
            className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800/60 hover:text-amber-300 transition-colors"
          >
            <span>⚔️</span>
            <span>My Creations</span>
          </Link>
          <Link
            to="/profile?tab=bookmarks"
            onClick={handleClose}
            className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800/60 hover:text-amber-300 transition-colors"
          >
            <span>⭐</span>
            <span>Bookmarks</span>
          </Link>
          <div className="border-t border-zinc-800/80 my-1" />
          <button
            onClick={handleSignOut}
            className="w-full text-left flex items-center gap-2 px-4 py-2 hover:bg-red-950/40 text-red-400 hover:text-red-300 transition-colors"
          >
            <span>🚪</span>
            <span>Sign Out</span>
          </button>
        </div>
      )}
    </div>
  );
};
