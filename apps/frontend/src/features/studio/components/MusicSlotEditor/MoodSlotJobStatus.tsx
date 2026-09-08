import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { AudioPreviewPlayer } from "@/shared/components/AudioPreviewPlayer";
import { MusicGenerationJob } from "../../types/music.types";

interface MoodSlotJobStatusProps {
  job: MusicGenerationJob;
  isConfirming: boolean;
  onConfirm: () => void;
  onDiscard: () => void;
}

const JobInProgress: React.FC = () => (
  <p className="text-xs text-content-muted flex items-center gap-2">
    <span className="h-3 w-3 animate-spin rounded-full border-2 border-content-muted border-t-transparent" />
    Generating…
  </p>
);

const JobSucceeded: React.FC<{
  previewUrl?: string | null;
  isConfirming: boolean;
  onConfirm: () => void;
  onDiscard: () => void;
}> = ({ previewUrl, isConfirming, onConfirm, onDiscard }) => {
  if (!previewUrl) {
    return (
      <>
        <p className="text-xs text-danger">
          Track generated, but preview is unavailable.
        </p>
        <Button type="button" variant="ghost" size="sm" onClick={onDiscard}>
          Discard
        </Button>
      </>
    );
  }
  return (
    <>
      <AudioPreviewPlayer src={previewUrl} />
      <div className="flex gap-2">
        <Button
          type="button"
          variant="primary"
          size="sm"
          disabled={isConfirming}
          onClick={onConfirm}
        >
          {isConfirming ? "Saving…" : "Confirm"}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDiscard}>
          Discard
        </Button>
      </div>
    </>
  );
};

export const MoodSlotJobStatus: React.FC<MoodSlotJobStatusProps> = ({
  job,
  isConfirming,
  onConfirm,
  onDiscard,
}) => {
  const isRunning = job.status === "pending" || job.status === "running";

  return (
    <div className="space-y-2 pt-2 border-t border-border-subtle">
      {isRunning && <JobInProgress />}
      {job.status === "succeeded" && (
        <JobSucceeded
          previewUrl={job.preview_url}
          isConfirming={isConfirming}
          onConfirm={onConfirm}
          onDiscard={onDiscard}
        />
      )}
      {job.status === "failed" && (
        <>
          <p className="text-xs text-danger">
            {job.error_message || "Generation failed."}
          </p>
          <Button type="button" variant="ghost" size="sm" onClick={onDiscard}>
            Dismiss
          </Button>
        </>
      )}
    </div>
  );
};
