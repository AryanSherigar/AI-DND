import React, { useEffect, useState } from "react";
import { useStudioStore } from "../../stores/studio.store";
import { GENRES } from "../../../../shared/constants/genres";
import { CoverImageUploader } from "../CoverImageUploader/CoverImageUploader";

export const Step1Meta: React.FC = () => {
  const { newbieDraft, updateNewbieDraft } = useStudioStore();
  const [localTitle, setLocalTitle] = useState(newbieDraft.title);
  const [localLogline, setLocalLogline] = useState(newbieDraft.logline);

  // Sync external changes (e.g. from AI Assistant) into local inputs
  useEffect(() => {
    setLocalTitle(newbieDraft.title);
  }, [newbieDraft.title]);

  useEffect(() => {
    setLocalLogline(newbieDraft.logline);
  }, [newbieDraft.logline]);

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextTitle = e.target.value;
    setLocalTitle(nextTitle);
    updateNewbieDraft({ title: nextTitle });
  };

  const handleLoglineChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const nextLogline = e.target.value;
    setLocalLogline(nextLogline);
    updateNewbieDraft({ logline: nextLogline });
  };

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
      <div className="space-y-2 border-b border-border-subtle pb-4">
        <h2 className="text-2xl font-semibold text-content tracking-tight">
          The Basics
        </h2>
        <p className="text-sm text-content-muted">
          Set the foundational details for your world.
        </p>
      </div>

      {/* Title */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
          Scenario Title *
        </label>
        <input
          type="text"
          value={localTitle}
          onChange={handleTitleChange}
          placeholder="e.g., The Whispering Caverns"
          className="w-full rounded-lg border border-border-subtle bg-surface-inset px-4 py-3 font-sans text-sm text-content placeholder:text-content-faint transition-colors focus-visible:border-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
        />
      </div>

      {/* Logline */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
          Logline / Summary
        </label>
        <textarea
          value={localLogline}
          onChange={handleLoglineChange}
          rows={2}
          placeholder="A short hook describing the central adventure, threat, or atmosphere..."
          className="w-full rounded-lg border border-border-subtle bg-surface-inset px-4 py-3 font-sans text-sm text-content placeholder:text-content-faint transition-colors focus-visible:border-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 resize-none"
        />
      </div>

      {/* Genre Tags */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
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
                className={`rounded-md px-3 py-1 text-xs font-mono border transition-colors ${
                  isSelected
                    ? "bg-content text-surface border-content font-semibold"
                    : "bg-surface-inset text-content-muted border-border-subtle hover:border-border-strong hover:text-content"
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
        <CoverImageUploader
          label="Cover Image"
          value={newbieDraft.cover_image_url}
          onChange={(url) => updateNewbieDraft({ cover_image_url: url || "" })}
          generatePrompt={{
            title: newbieDraft.title,
            genreTags: newbieDraft.genre_tags || [],
            openingScene: newbieDraft.logline,
          }}
        />
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
            Estimated Playtime
          </label>
          <select
            value={newbieDraft.estimated_playtime}
            onChange={(e) =>
              updateNewbieDraft({ estimated_playtime: e.target.value })
            }
            className="w-full rounded-lg border border-border-subtle bg-surface-inset px-4 py-3 font-sans text-sm text-content transition-colors focus-visible:border-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
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
          <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
            Complexity Tier
          </label>
          <div className="flex rounded-md bg-surface-inset p-1 border border-border-subtle">
            <div className="px-4 py-2 rounded-sm bg-content text-surface text-xs font-bold uppercase tracking-wider flex-1 text-center">
              Newbie
            </div>
          </div>
        </div>
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
            Player Count
          </label>
          <div className="flex rounded-md bg-surface-inset p-1 border border-border-subtle">
            {(["solo", "multiplayer", "both"] as const).map((count) => (
              <button
                key={count}
                type="button"
                onClick={() =>
                  updateNewbieDraft({ player_count_support: count })
                }
                className={`flex-1 px-2 py-2 text-xs font-semibold uppercase tracking-wider rounded-sm transition-colors ${
                  newbieDraft.player_count_support === count
                    ? "bg-content text-surface"
                    : "text-content-faint hover:text-content-muted"
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
