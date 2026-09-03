import React from "react";
import { GENRES } from "@/shared/constants/genres";

interface GenreTagsPickerProps {
  selected: string[];
  onChange: (genres: string[]) => void;
}

export const GenreTagsPicker: React.FC<GenreTagsPickerProps> = ({
  selected,
  onChange,
}) => {
  const handleToggle = (genre: string): void => {
    const isSelected = selected.includes(genre);
    if (isSelected) {
      onChange(selected.filter((tag) => tag !== genre));
      return;
    }
    onChange([...selected, genre]);
  };

  return (
    <div className="flex flex-wrap gap-2">
      {GENRES.map((genre) => {
        const isSelected = selected.includes(genre);
        return (
          <button
            key={genre}
            type="button"
            onClick={() => handleToggle(genre)}
            className={`px-3 py-1 text-xs font-mono border transition-colors ${
              isSelected
                ? "bg-zinc-100 text-zinc-950 border-zinc-100 font-semibold"
                : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-600 hover:text-zinc-200"
            }`}
          >
            {genre}
          </button>
        );
      })}
    </div>
  );
};
