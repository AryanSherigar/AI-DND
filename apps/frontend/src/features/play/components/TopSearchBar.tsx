import React, { useState, useEffect } from "react";

interface TopSearchBarProps {
  searchParams: URLSearchParams;
  onSearchUpdate: (query: string) => void;
  onPillSelect: (filterKey: string, value: string) => void;
  onOpenAdvanced: () => void;
  onClearFilters: () => void;
}

const PILLS = [
  { label: "All", filterKey: "mode", value: "all" },
  { label: "Newbie Mode", filterKey: "mode", value: "newbie" },
  { label: "Master Mode", filterKey: "mode", value: "master" },
  { label: "Solo", filterKey: "playerCount", value: "solo" },
  { label: "Multiplayer", filterKey: "playerCount", value: "multiplayer" },
  { label: "Popular", filterKey: "sort", value: "popular" },
  { label: "Trending", filterKey: "sort", value: "trending" },
];

export const TopSearchBar: React.FC<TopSearchBarProps> = ({
  searchParams,
  onSearchUpdate,
  onPillSelect,
  onOpenAdvanced,
  onClearFilters,
}) => {
  const [localQuery, setLocalQuery] = useState(searchParams.get("q") || "");

  // Sync local query if URL changes externally
  useEffect(() => {
    setLocalQuery(searchParams.get("q") || "");
  }, [searchParams]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearchUpdate(localQuery);
  };

  const isPillActive = (filterKey: string, value: string) => {
    const currentVal = searchParams.get(filterKey);
    if (value === "all" && !currentVal) return true; // 'All' is active if no specific filter is set
    return currentVal === value;
  };

  return (
    <div className="w-full bg-[#0d0f14] border-b border-zinc-800 z-10 sticky top-0 flex flex-col">
      {/* Search Input Row */}
      <div className="h-16 px-6 md:px-12 flex items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="flex-1 max-w-2xl relative">
          <input
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            placeholder="Search scenarios, worlds, or tags..."
            className="w-full bg-zinc-900 border border-zinc-800 text-white rounded-full py-2 pl-12 pr-4 font-mono text-sm focus:outline-none focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600 transition-all placeholder:text-zinc-600"
          />
          <button
            type="submit"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white transition-colors p-1"
          >
            {/* Minimal Search Icon SVG if PixelIcons isn't available */}
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          </button>
        </form>

        <button
          onClick={onOpenAdvanced}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-full text-zinc-300 font-mono text-sm transition-colors flex-shrink-0"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
          <span className="hidden sm:inline">Filters</span>
        </button>
      </div>

      {/* Quick Filter Pills Row */}
      <div className="h-14 px-6 md:px-12 flex items-center overflow-x-auto custom-scrollbar border-t border-zinc-800/50">
        <div className="flex gap-3">
          {PILLS.map((pill) => (
            <button
              key={`${pill.filterKey}-${pill.value}`}
              onClick={() => onPillSelect(pill.filterKey, pill.value)}
              className={`whitespace-nowrap px-4 py-1.5 rounded-lg text-sm font-mono transition-colors ${
                isPillActive(pill.filterKey, pill.value)
                  ? "bg-zinc-200 text-[#0d0f14] font-semibold"
                  : "bg-zinc-900 text-zinc-400 border border-zinc-800 hover:bg-zinc-800 hover:text-zinc-200"
              }`}
            >
              {pill.label}
            </button>
          ))}

          {/* Clear All Button */}
          <button
            onClick={onClearFilters}
            className="whitespace-nowrap px-4 py-1.5 rounded-lg text-sm font-mono transition-colors text-red-400 bg-red-500/10 hover:bg-red-500/20"
          >
            Clear All
          </button>
        </div>
      </div>
    </div>
  );
};
