import React, { useEffect, useState } from "react";
import { useStudioStore } from "../../stores/studio.store";

export const Step1Meta: React.FC = () => {
  const { newbieDraft, updateNewbieDraft, setSaveState } = useStudioStore();
  const [localTitle, setLocalTitle] = useState(newbieDraft.title);

  // Auto-save logic (debounced)
  useEffect(() => {
    const handler = setTimeout(() => {
      if (localTitle !== newbieDraft.title) {
        setSaveState(true);
        // Simulate API call delay
        setTimeout(() => {
          updateNewbieDraft({ title: localTitle });
          setSaveState(false, new Date());
        }, 500);
      }
    }, 1000);
    return () => clearTimeout(handler);
  }, [localTitle, newbieDraft.title, updateNewbieDraft, setSaveState]);

  return (
    <div className="space-y-8">
      <div className="space-y-2 border-b border-zinc-800 pb-4">
        <h2 className="text-2xl font-semibold text-zinc-100 tracking-tight">The Basics</h2>
        <p className="text-sm text-zinc-400">Set the foundational details for your world.</p>
      </div>
      
      {/* Form Fields */}
      {/* Title */}
      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">Scenario Title</label>
        <input 
          type="text" 
          value={localTitle} 
          onChange={(e) => setLocalTitle(e.target.value)}
          placeholder="e.g., The Ashen Wastes"
          className="w-full bg-zinc-950 border border-zinc-700 rounded-none px-4 py-3 text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-300 transition-colors font-sans text-sm"
        />
      </div>

      {/* Cover Image & Playtime (placeholder UI) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">Cover Image URL</label>
          <input 
            type="text" 
            value={newbieDraft.cover_image_url} 
            onChange={(e) => updateNewbieDraft({ cover_image_url: e.target.value })}
            placeholder="https://..."
            className="w-full bg-zinc-950 border border-zinc-700 rounded-none px-4 py-3 text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-300 transition-colors font-sans text-sm"
          />
        </div>
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">Estimated Playtime</label>
          <select 
            value={newbieDraft.estimated_playtime}
            onChange={(e) => updateNewbieDraft({ estimated_playtime: e.target.value })}
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
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">Complexity Tier</label>
          <div className="flex bg-zinc-950 p-1 border border-zinc-800 rounded-none">
             {/* Just a read-only badge since we're in newbie mode */}
             <div className="px-4 py-2 bg-zinc-100 text-zinc-950 rounded-none text-xs font-bold uppercase tracking-wider flex-1 text-center">Newbie</div>
          </div>
        </div>
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">Player Count</label>
          <div className="flex bg-zinc-950 p-1 border border-zinc-800 rounded-none">
            {['solo', 'multiplayer', 'both'].map((count) => (
              <button
                key={count}
                onClick={() => updateNewbieDraft({ player_count_support: count as any })}
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
