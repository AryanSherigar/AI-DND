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
            className={`rounded-md border px-3 py-1.5 font-sans text-xs transition-colors ${
              isSelected
                ? "border-content bg-content font-semibold text-surface"
                : "border-border-subtle bg-surface-inset text-content-muted hover:border-border-strong hover:text-content"
            }`}
          >
            {genre}
          </button>
        );
      })}
    </div>
  );
};
