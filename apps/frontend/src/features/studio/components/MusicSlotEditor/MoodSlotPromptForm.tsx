import React from "react";
import { Button } from "@/shared/components/ui/Button";

interface MoodSlotPromptFormProps {
  prompt: string;
  onPromptChange: (val: string) => void;
  isBusy: boolean;
  quotaExceeded: boolean;
  isRequesting: boolean;
  onGenerate: () => void;
}

export const MoodSlotPromptForm: React.FC<MoodSlotPromptFormProps> = ({
  prompt,
  onPromptChange,
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
      <p className="text-xs text-content-faint">
        Generates a ~30s loopable clip.
      </p>
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
