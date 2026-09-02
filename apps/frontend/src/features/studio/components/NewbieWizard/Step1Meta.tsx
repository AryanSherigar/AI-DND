import React, { useEffect, useState } from "react";
import { useStudioStore } from "../../stores/studio.store";
import { GENRES } from "../../../../shared/constants/genres";

export const Step1Meta: React.FC = () => {
  const { newbieDraft, updateNewbieDraft } = useStudioStore();
  const [localTitle, setLocalTitle] = useState(newbieDraft.title);
  const [localLogline, setLocalLogline] = useState(newbieDraft.logline);

  // Sync state to studio store on change
  useEffect(() => {
    updateNewbieDraft({ title: localTitle, logline: localLogline });
  }, [localTitle, localLogline, updateNewbieDraft]);

  const toggleGenre = (genre: string) => {
    const current = newbieDraft.genre_tags || [];
    const exists = current.includes(genre);
    const updated = exists
      ? current.filter((g) => g !== genre)
      : [...current, genre];
    updateNewbieDraft({ genre_tags: updated });
  };

  return (
    <div className="space-y-8">
      <div className="space-y-2 border-b border-zinc-800 pb-4">
        <h2 className="text-2xl font-semibold text-zinc-100 tracking-tight">
          The Basics
        </h2>
        <p className="text-sm text-zinc-400">
          Set the foundational details for your world.
        </p>
      </div>

      {/* Title */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          Scenario Title *
        </label>
        <input
          type="text"
          value={localTitle}
          onChange={(e) => setLocalTitle(e.target.value)}
          placeholder="e.g., The Whispering Caverns"
          className="w-full bg-zinc-950 border border-zinc-700 rounded-none px-4 py-3 text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-300 transition-colors font-sans text-sm"
        />
      </div>

      {/* Logline */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          Logline / Summary
        </label>
        <textarea
          value={localLogline}
          onChange={(e) => setLocalLogline(e.target.value)}
          rows={2}
          placeholder="A short hook describing the central adventure, threat, or atmosphere..."
          className="w-full bg-zinc-950 border border-zinc-700 rounded-none px-4 py-3 text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-300 transition-colors font-sans text-sm resize-none"
        />
      </div>

      {/* Genre Tags */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          Genre Tags
        </label>
        <div className="flex flex-wrap gap-2">
          {GENRES.map((g) => {
            const isSelected = newbieDraft.genre_tags?.includes(g);
            return (
              <button
                key={g}
                type="button"
                onClick={() => toggleGenre(g)}
                className={`px-3 py-1 text-xs font-mono border transition-colors ${
                  isSelected
                    ? "bg-zinc-100 text-zinc-950 border-zinc-100 font-semibold"
                    : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-600 hover:text-zinc-200"
                }`}
              >
                {g}
              </button>
            );
          })}
        </div>
      </div>

      {/* Cover Image & Playtime */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
            Cover Image URL
          </label>
          <input
            type="text"
            value={newbieDraft.cover_image_url}
            onChange={(e) =>
              updateNewbieDraft({ cover_image_url: e.target.value })
            }
            placeholder="https://..."
            className="w-full bg-zinc-950 border border-zinc-700 rounded-none px-4 py-3 text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-300 transition-colors font-sans text-sm"
          />
        </div>
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
            Estimated Playtime
          </label>
          <select
            value={newbieDraft.estimated_playtime}
            onChange={(e) =>
              updateNewbieDraft({ estimated_playtime: e.target.value })
            }
            className="w-full bg-zinc-950 border border-zinc-700 rounded-none px-4 py-3 text-zinc-100 focus:outline-none focus:border-zinc-300 transition-colors font-sans text-sm"
          >
            <option value="">Select playtime...</option>
            <option value="short">Short (1-2 hours)</option>
            <option value="medium">Medium (2-5 hours)</option>
            <option value="long">Long (Campaign)</option>
          </select>
        </div>
      </div>

      {/* Tiers & Player Count */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
            Complexity Tier
          </label>
          <div className="flex bg-zinc-950 p-1 border border-zinc-800 rounded-none">
            <div className="px-4 py-2 bg-zinc-100 text-zinc-950 rounded-none text-xs font-bold uppercase tracking-wider flex-1 text-center">
              Newbie
            </div>
          </div>
        </div>
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
            Player Count
          </label>
          <div className="flex bg-zinc-950 p-1 border border-zinc-800 rounded-none">
            {["solo", "multiplayer", "both"].map((count) => (
              <button
                key={count}
                type="button"
                onClick={() =>
                  updateNewbieDraft({ player_count_support: count as any })
                }
                className={`flex-1 px-2 py-2 text-xs font-semibold uppercase tracking-wider rounded-none transition-colors ${
                  newbieDraft.player_count_support === count
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {count.charAt(0).toUpperCase() + count.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
