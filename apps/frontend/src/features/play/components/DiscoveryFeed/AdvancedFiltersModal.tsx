import React from "react";
import { GENRES } from "../../../../shared/constants/genres";

interface AdvancedFiltersModalProps {
  isOpen: boolean;
  onClose: () => void;
  searchParams: URLSearchParams;
  onApply: (newParams: URLSearchParams) => void;
}

export const AdvancedFiltersModal: React.FC<AdvancedFiltersModalProps> = ({
  isOpen,
  onClose,
  searchParams,
  onApply,
}) => {
  if (!isOpen) return null;

  // Local state for modal before applying
  const [localParams, setLocalParams] = React.useState(
    new URLSearchParams(searchParams),
  );

  const handleToggleGenre = (genre: string) => {
    const genres = localParams.getAll("genre");
    if (genres.includes(genre)) {
      localParams.delete("genre");
      genres
        .filter((g) => g !== genre)
        .forEach((g) => localParams.append("genre", g));
    } else {
      localParams.append("genre", genre);
    }
    setLocalParams(new URLSearchParams(localParams));
  };

  const handleApply = () => {
    onApply(localParams);
    onClose();
  };

  const handleClear = () => {
    const cleared = new URLSearchParams();
    if (localParams.get("q")) cleared.set("q", localParams.get("q")!);
    setLocalParams(cleared);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#0d0f14] border border-zinc-800 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl">
        <div className="flex justify-between items-center p-6 border-b border-zinc-800">
          <h2 className="text-xl font-fell-sc font-bold text-white tracking-wider">
            Advanced Filters
          </h2>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-white transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          {/* Complexity Tier */}
          <section>
            <h3 className="text-sm font-mono text-zinc-400 mb-3 uppercase tracking-widest">
              Complexity
            </h3>
            <div className="flex gap-3">
              {["newbie", "intermediate", "master"].map((tier) => (
                <button
                  key={tier}
                  onClick={() => {
                    localParams.set("mode", tier);
                    setLocalParams(new URLSearchParams(localParams));
                  }}
                  className={`px-4 py-2 rounded-lg font-mono text-sm capitalize border ${
                    localParams.get("mode") === tier
                      ? "bg-emerald-500/20 border-emerald-500 text-emerald-400"
                      : "bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-600"
                  }`}
                >
                  {tier}
                </button>
              ))}
            </div>
          </section>

          {/* Genres (Multi-select) */}
          <section>
            <h3 className="text-sm font-mono text-zinc-400 mb-3 uppercase tracking-widest">
              Genres
            </h3>
            <div className="flex flex-wrap gap-2">
              {GENRES.map((genre) => {
                const isActive = localParams
                  .getAll("genre")
                  .includes(genre.toLowerCase());
                return (
                  <button
                    key={genre}
                    onClick={() => handleToggleGenre(genre.toLowerCase())}
                    className={`px-3 py-1.5 rounded-full font-mono text-xs border ${
                      isActive
                        ? "bg-zinc-200 border-zinc-200 text-[#0d0f14] font-semibold"
                        : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800"
                    }`}
                  >
                    {genre}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Minimum Plays */}
          <section>
            <h3 className="text-sm font-mono text-zinc-400 mb-3 uppercase tracking-widest">
              Minimum Plays
            </h3>
            <select
              value={localParams.get("minPlays") || "0"}
              onChange={(e) => {
                if (e.target.value === "0") localParams.delete("minPlays");
                else localParams.set("minPlays", e.target.value);
                setLocalParams(new URLSearchParams(localParams));
              }}
              className="w-full max-w-xs bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-lg p-2 font-mono text-sm focus:outline-none focus:border-zinc-500"
            >
              <option value="0">Any</option>
              <option value="100">100+</option>
              <option value="500">500+</option>
              <option value="1000">1000+</option>
              <option value="5000">5000+</option>
            </select>
          </section>
        </div>

        <div className="p-6 border-t border-zinc-800 flex justify-between items-center bg-zinc-950/50">
          <button
            onClick={handleClear}
            className="text-sm font-mono text-zinc-500 hover:text-zinc-300"
          >
            Clear all
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-5 py-2 rounded-lg font-mono text-sm border border-zinc-800 text-zinc-300 hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              onClick={handleApply}
              className="px-5 py-2 rounded-lg font-mono text-sm font-bold bg-white text-black hover:bg-zinc-200 shadow-[0_0_15px_rgba(255,255,255,0.2)]"
            >
              Show Results
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
