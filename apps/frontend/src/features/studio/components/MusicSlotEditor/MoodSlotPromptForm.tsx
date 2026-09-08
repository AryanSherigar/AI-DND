import React from "react";
import { Button } from "@/shared/components/ui/Button";

const MIN_DURATION = 30;
const MAX_DURATION = 120;

interface MoodSlotPromptFormProps {
  prompt: string;
  onPromptChange: (val: string) => void;
  durationSeconds: number;
  onDurationChange: (val: number) => void;
  isBusy: boolean;
  quotaExceeded: boolean;
  isRequesting: boolean;
  onGenerate: () => void;
}

export const MoodSlotPromptForm: React.FC<MoodSlotPromptFormProps> = ({
  prompt,
  onPromptChange,
  durationSeconds,
  onDurationChange,
  isBusy,
  quotaExceeded,
  isRequesting,
  onGenerate,
}) => (
  <div className="space-y-2 pt-2 border-t border-border-subtle">
    <textarea
      value={prompt}
      onChange={(e) => onPromptChange(e.target.value)}
      disabled={isBusy || quotaExceeded}
      placeholder="Describe the track to generate (e.g. slow, tense strings)…"
      className="w-full rounded-md border border-border-subtle bg-surface p-2 text-xs text-content"
      rows={2}
      maxLength={500}
    />
    <div className="flex items-center gap-2">
      <label className="text-xs text-content-faint">
        Length (s)
        <input
          type="number"
          min={MIN_DURATION}
          max={MAX_DURATION}
          value={durationSeconds}
          onChange={(e) => onDurationChange(Number(e.target.value))}
          disabled={isBusy || quotaExceeded}
          className="ml-2 w-16 rounded-md border border-border-subtle bg-surface px-1.5 py-1 text-xs text-content"
        />
      </label>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={isBusy || quotaExceeded || !prompt.trim()}
        onClick={onGenerate}
      >
        {isRequesting ? "Submitting…" : "Generate with AI"}
      </Button>
    </div>
    {quotaExceeded && (
      <p className="text-xs text-content-faint">
        Generation quota reached for this scenario or today.
      </p>
    )}
  </div>
);
