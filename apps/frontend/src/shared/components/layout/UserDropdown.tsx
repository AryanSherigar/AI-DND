import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  IconUser,
  IconPencil,
  IconBookmark,
  IconLogout,
  IconChevronDown,
} from "@tabler/icons-react";
import { UserDropdownProps } from "./Header.types";

const MENU_ITEMS = [
  { to: "/profile", label: "Profile", Icon: IconUser },
  { to: "/profile?tab=creations", label: "My creations", Icon: IconPencil },
  { to: "/profile?tab=bookmarks", label: "Bookmarks", Icon: IconBookmark },
];

export const UserDropdown: React.FC<UserDropdownProps> = ({
  user,
  onLogout,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent): void => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent): void => {
      if (event.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const handleToggle = (): void => setIsOpen((prev) => !prev);
  const handleClose = (): void => setIsOpen(false);
  const handleSignOut = (): void => {
    setIsOpen(false);
    onLogout();
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={handleToggle}
        aria-expanded={isOpen}
        aria-haspopup="true"
        className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-1.5 font-sans text-sm text-content-muted transition hover:bg-surface-overlay hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <span className="max-w-[140px] truncate font-medium">
          {user.display_name || "Adventurer"}
        </span>
        <IconChevronDown size={14} className="text-content-faint" />
      </button>

      {isOpen && (
        <div className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-lg border border-border-subtle bg-surface-overlay py-1 font-sans text-sm text-content-muted shadow-elevated">
          {MENU_ITEMS.map(({ to, label, Icon }) => (
            <Link
              key={to}
              to={to}
              onClick={handleClose}
              className="flex items-center gap-2.5 px-4 py-2 transition-colors hover:bg-surface-raised hover:text-content"
            >
              <Icon size={16} className="text-content-faint" />
              {label}
            </Link>
          ))}
          <div className="my-1 h-px bg-border-subtle" />
          <button
            onClick={handleSignOut}
            className="flex w-full items-center gap-2.5 px-4 py-2 text-left text-danger transition-colors hover:bg-danger/10"
          >
            <IconLogout size={16} />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
};
