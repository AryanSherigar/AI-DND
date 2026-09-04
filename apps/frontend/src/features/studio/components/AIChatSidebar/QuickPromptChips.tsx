import React from "react";

export interface QuickPromptChipsProps {
  activeSection: string;
  onSelectPrompt: (prompt: string) => void;
  disabled?: boolean;
}

const SECTION_PROMPTS: Record<string, string[]> = {
  meta: [
    "Suggest 3 catchy scenario titles",
    "Draft a compelling 2-sentence logline",
    "Recommend genre tags for my world",
  ],
  lore: [
    "Brainstorm 3 unique factions",
    "Draft a central conflict & goal",
    "Write an evocative opening scene hook",
    "Create a memorable character card",
  ],
  setup: [
    "Suggest character class options",
    "Suggest player origin choices",
    "Draft starting equipment choices",
  ],
  narrator: [
    "Suggest a dark fantasy narrative style",
    "Write strict AI narrator guardrails",
    "Suggest a gritty, atmospheric voice",
  ],
  review: [
    "Review my scenario lore for plot holes",
    "Suggest missing details before publishing",
    "Draft exciting turn 1 ideas",
  ],
};

export const QuickPromptChips: React.FC<QuickPromptChipsProps> = ({
  activeSection,
  onSelectPrompt,
  disabled = false,
}) => {
  const prompts = SECTION_PROMPTS[activeSection] || SECTION_PROMPTS.meta;

  return (
    <div className="flex gap-1.5 overflow-x-auto py-1 px-3 no-scrollbar">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          type="button"
          disabled={disabled}
          onClick={() => onSelectPrompt(prompt)}
          className="shrink-0 text-[11px] font-mono px-2 py-1 bg-zinc-900/90 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800 hover:border-zinc-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          + {prompt}
        </button>
      ))}
    </div>
  );
};
