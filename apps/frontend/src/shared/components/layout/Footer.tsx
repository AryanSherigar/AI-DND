import React from "react";
import { Link } from "react-router-dom";
import { IconBrandGithub } from "@tabler/icons-react";

const PRODUCT_LINKS = [
  { to: "/discover", label: "Discover" },
  { to: "/studio", label: "Studio" },
  { to: "/profile", label: "Profile" },
];

const LEGAL_LINKS = [
  { to: "/terms", label: "Terms" },
  { to: "/privacy", label: "Privacy" },
];

const GITHUB_URL = "https://github.com/AryanSherigar/AI-DND";

export const Footer: React.FC = () => {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border-subtle bg-surface">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-10 md:flex-row md:items-center md:justify-between md:gap-4">
        <div className="flex flex-col gap-1">
          <Link
            to="/"
            className="font-mono text-lg font-semibold lowercase tracking-[0.3em] text-content"
          >
            wevr
          </Link>
          <p className="max-w-xs font-sans text-xs leading-relaxed text-content-faint">
            Weave your own worlds and stories.
          </p>
        </div>

        <nav className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {[...PRODUCT_LINKS, ...LEGAL_LINKS].map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="font-sans text-sm text-content-muted transition-colors hover:text-content"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-4">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="wevr on GitHub"
            className="text-content-faint transition-colors hover:text-content"
          >
            <IconBrandGithub size={18} />
          </a>
          <span className="font-mono text-xs text-content-faint">
            © {year} wevr
          </span>
        </div>
      </div>
    </footer>
  );
};
