import React, { useEffect, useState } from "react";
import { useStudioStore } from "../../stores/studio.store";
import { DistractionFreeEditor } from "../MarkdownEditor/DistractionFreeEditor";

export const Step2Lore: React.FC = () => {
  const { newbieDraft, updateNewbieDraft, setSaveState } = useStudioStore();
  const [localDraft, setLocalDraft] = useState({
    useSingleLorePrompt: newbieDraft.useSingleLorePrompt,
    worldLore: newbieDraft.worldLore,
    openingPrompt: newbieDraft.openingPrompt,
    mainConflict: newbieDraft.mainConflict,
    includeConflict: newbieDraft.includeConflict,
    storyCards: newbieDraft.storyCards,
    singleLorePrompt: newbieDraft.singleLorePrompt,
  });

  // Debounced auto-save
  useEffect(() => {
    const handler = setTimeout(() => {
      const changed = Object.keys(localDraft).some(
        (key) =>
          localDraft[key as keyof typeof localDraft] !==
          newbieDraft[key as keyof typeof newbieDraft],
      );
      if (changed) {
        setSaveState(true);
        setTimeout(() => {
          updateNewbieDraft(localDraft);
          setSaveState(false, new Date());
        }, 500);
      }
    }, 1000);
    return () => clearTimeout(handler);
  }, [localDraft, newbieDraft, updateNewbieDraft, setSaveState]);

  const handleChange = (field: keyof typeof localDraft, value: any) => {
    setLocalDraft((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="space-y-8">
      <div className="space-y-2 border-b border-zinc-800 pb-4 flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-100 tracking-tight">
            World Lore
          </h2>
          <p className="text-sm text-zinc-400">
            Describe the world, characters, and history.
          </p>
        </div>

        <div className="flex items-center gap-3 bg-zinc-950 border border-zinc-800 p-2">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Single Prompt Mode
          </span>
          <button
            onClick={() =>
              handleChange(
                "useSingleLorePrompt",
                !localDraft.useSingleLorePrompt,
              )
            }
            className={`w-10 h-5 relative transition-colors border border-zinc-700 ${localDraft.useSingleLorePrompt ? "bg-zinc-200" : "bg-zinc-900"}`}
          >
            <div
              className={`absolute top-0.5 left-0.5 w-3.5 h-3.5 bg-zinc-500 transition-transform ${localDraft.useSingleLorePrompt ? "translate-x-5 bg-zinc-800" : "translate-x-0"}`}
            ></div>
          </button>
        </div>
      </div>

      {localDraft.useSingleLorePrompt ? (
        <div className="space-y-3">
          <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
            Everything
          </label>
          <DistractionFreeEditor
            value={localDraft.singleLorePrompt}
            onChange={(val) => handleChange("singleLorePrompt", val)}
            placeholder="Dump everything here..."
            className="h-[60vh]"
          />
        </div>
      ) : (
        <div className="space-y-8">
          <div className="space-y-3">
            <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
              The World Lore
            </label>
            <DistractionFreeEditor
              value={localDraft.worldLore}
              onChange={(val) => handleChange("worldLore", val)}
              placeholder="The world of Elyria was forged in dragonfire..."
              className="h-48"
            />
          </div>

          <div className="space-y-3">
            <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
              Opening Prompt
            </label>
            <p className="text-xs text-zinc-500">
              How does the story begin for the player?
            </p>
            <DistractionFreeEditor
              value={localDraft.openingPrompt}
              onChange={(val) => handleChange("openingPrompt", val)}
              placeholder="You wake up in a damp cell, the sound of dripping water echoing..."
              className="h-32"
            />
          </div>

          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
                Main Conflict / Goal
              </label>
              <button
                onClick={() =>
                  handleChange("includeConflict", !localDraft.includeConflict)
                }
                className={`text-xs font-semibold px-3 py-1 transition-colors uppercase tracking-wider border ${localDraft.includeConflict ? "bg-zinc-800 text-zinc-200 border-zinc-700" : "bg-zinc-950 text-zinc-500 border-zinc-800 hover:text-zinc-300"}`}
              >
                {localDraft.includeConflict ? "Enabled" : "Disabled"}
              </button>
            </div>
            {localDraft.includeConflict && (
              <DistractionFreeEditor
                value={localDraft.mainConflict}
                onChange={(val) => handleChange("mainConflict", val)}
                placeholder="The player must find the hidden artifact before the eclipse..."
                className="h-32 animate-in slide-in-from-top-2 duration-300"
              />
            )}
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
                  Story Cards
                </label>
                <p className="text-xs text-zinc-500">
                  Create separate cards for different characters, factions, or
                  locations.
                </p>
              </div>
              <button
                onClick={() =>
                  handleChange("storyCards", [
                    ...localDraft.storyCards,
                    {
                      id: Math.random().toString(36).substring(7),
                      type: "Character",
                      name: "New Card",
                      content: "",
                    },
                  ])
                }
                className="px-3 py-1.5 bg-zinc-900 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 border border-zinc-700 text-xs font-semibold uppercase tracking-wider transition-colors"
              >
                + Add Card
              </button>
            </div>

            <div className="space-y-6">
              {localDraft.storyCards.map((card, idx) => (
                <div
                  key={card.id}
                  className="bg-zinc-950 border border-zinc-800 p-4 space-y-3 relative group"
                >
                  <button
                    onClick={() =>
                      handleChange(
                        "storyCards",
                        localDraft.storyCards.filter((c) => c.id !== card.id),
                      )
                    }
                    className="absolute top-4 right-4 text-zinc-500 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                  <div className="flex gap-3 mb-2 w-full md:w-2/3">
                    <select
                      value={card.type}
                      onChange={(e) => {
                        const newCards = [...localDraft.storyCards];
                        newCards[idx].type = e.target.value;
                        handleChange("storyCards", newCards);
                      }}
                      className="bg-transparent border-b border-zinc-800 text-sm font-semibold text-zinc-400 focus:outline-none focus:border-zinc-400 pb-1"
                    >
                      <option
                        value="Character"
                        className="bg-zinc-950 text-zinc-300"
                      >
                        Character
                      </option>
                      <option
                        value="Faction"
                        className="bg-zinc-950 text-zinc-300"
                      >
                        Faction
                      </option>
                      <option
                        value="Location"
                        className="bg-zinc-950 text-zinc-300"
                      >
                        Location
                      </option>
                      <option
                        value="Item"
                        className="bg-zinc-950 text-zinc-300"
                      >
                        Item
                      </option>
                      <option
                        value="Other"
                        className="bg-zinc-950 text-zinc-300"
                      >
                        Other
                      </option>
                    </select>
                    <input
                      type="text"
                      value={card.name}
                      onChange={(e) => {
                        const newCards = [...localDraft.storyCards];
                        newCards[idx].name = e.target.value;
                        handleChange("storyCards", newCards);
                      }}
                      className="flex-1 bg-transparent border-b border-zinc-800 text-sm font-semibold text-zinc-100 focus:outline-none focus:border-zinc-400 pb-1"
                      placeholder="Name (e.g., Elara, Crimson Guild)"
                    />
                  </div>
                  <DistractionFreeEditor
                    value={card.content}
                    onChange={(val) => {
                      const newCards = [...localDraft.storyCards];
                      newCards[idx].content = val;
                      handleChange("storyCards", newCards);
                    }}
                    placeholder="Describe this character, faction, or location..."
                    className="h-32 bg-zinc-950/50"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
