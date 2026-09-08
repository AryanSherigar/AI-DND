import React, { useState, useEffect } from "react";
import { IconSearch, IconAdjustmentsHorizontal } from "@tabler/icons-react";

interface TopSearchBarProps {
  searchParams: URLSearchParams;
  onSearchUpdate: (query: string) => void;
  onPillSelect: (filterKey: string, value: string) => void;
  onOpenAdvanced: () => void;
  onClearFilters: () => void;
}

const PILLS = [
  { label: "All", filterKey: "mode", value: "all" },
  { label: "Newbie", filterKey: "mode", value: "newbie" },
  { label: "Master", filterKey: "mode", value: "master" },
  { label: "Solo", filterKey: "playerCount", value: "solo" },
  { label: "Multiplayer", filterKey: "playerCount", value: "multiplayer" },
  { label: "Popular", filterKey: "sort", value: "popular" },
  { label: "Trending", filterKey: "sort", value: "trending" },
];

const FILTER_KEYS = ["mode", "playerCount", "sort", "genre", "q"];

export const TopSearchBar: React.FC<TopSearchBarProps> = ({
  searchParams,
  onSearchUpdate,
  onPillSelect,
  onOpenAdvanced,
  onClearFilters,
}) => {
  const [localQuery, setLocalQuery] = useState(searchParams.get("q") || "");

  useEffect(() => {
    setLocalQuery(searchParams.get("q") || "");
  }, [searchParams]);

  const handleSearchSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    onSearchUpdate(localQuery);
  };

  const isPillActive = (filterKey: string, value: string): boolean => {
    const current = searchParams.get(filterKey);
    if (value === "all" && !current) return true;
    return current === value;
  };

  const hasActiveFilters = FILTER_KEYS.some((key) => searchParams.has(key));

  return (
    <div className="sticky top-0 z-10 flex w-full flex-col bg-surface-raised px-6 pt-16 md:px-10">
      <div className="flex items-center gap-3 pb-3">
        <form
          onSubmit={handleSearchSubmit}
          className="relative max-w-xl flex-1"
        >
          <IconSearch
            size={16}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-content-faint"
          />
          <input
            type="text"
            value={localQuery}
            onChange={(event) => setLocalQuery(event.target.value)}
            placeholder="Search scenarios, worlds, or tags…"
            className="w-full rounded-full border border-border-subtle bg-surface py-2 pl-10 pr-4 font-sans text-sm text-content transition placeholder:text-content-faint focus-visible:border-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
          />
        </form>

        <button
          onClick={onOpenAdvanced}
          className="flex flex-shrink-0 items-center gap-2 rounded-full border border-border-subtle bg-surface px-3.5 py-2 font-sans text-sm text-content-muted transition-colors hover:bg-surface-overlay hover:text-content"
        >
          <IconAdjustmentsHorizontal size={16} />
          <span className="hidden sm:inline">Filters</span>
        </button>
      </div>

      <div className="custom-scrollbar flex items-center gap-2 overflow-x-auto pb-3">
        {PILLS.map((pill) => (
          <button
            key={`${pill.filterKey}-${pill.value}`}
            onClick={() => onPillSelect(pill.filterKey, pill.value)}
            className={`whitespace-nowrap rounded-full px-3 py-1 font-sans text-sm transition-colors ${
              isPillActive(pill.filterKey, pill.value)
                ? "bg-content font-medium text-surface"
                : "text-content-muted hover:bg-surface hover:text-content"
            }`}
          >
            {pill.label}
          </button>
        ))}
        {hasActiveFilters && (
          <button
            onClick={onClearFilters}
            className="ml-1 whitespace-nowrap rounded-full px-3 py-1 font-sans text-sm text-content-faint transition-colors hover:text-danger"
          >
            Clear
          </button>
        )}
      </div>

      <div className="h-px w-full bg-border-subtle" />
    </div>
  );
};
