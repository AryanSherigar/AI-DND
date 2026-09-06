import React from "react";
import { DodgeDifficultySliderProps } from "./DodgeDifficultySlider.types";

const MIN_DIFFICULTY = 1;
const MAX_DIFFICULTY = 5;

export const DodgeDifficultySlider: React.FC<DodgeDifficultySliderProps> = ({
  value,
  onChange,
}) => {
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    onChange(Number(event.target.value));
  };

  return (
    <div className="space-y-1">
      <label htmlFor="dodge-difficulty" className="text-sm text-zinc-300">
        Difficulty ({value} / {MAX_DIFFICULTY})
      </label>
      <input
        id="dodge-difficulty"
        type="range"
        min={MIN_DIFFICULTY}
        max={MAX_DIFFICULTY}
        step={1}
        value={value}
        onChange={handleChange}
        aria-label="Dodge difficulty"
        className="w-full accent-zinc-100"
      />
      <div className="flex justify-between text-xs text-zinc-600">
        <span>Easy</span>
        <span>Brutal</span>
      </div>
    </div>
  );
};
