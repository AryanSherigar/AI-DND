import React, { useRef, useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { AudioPreviewPlayer } from "@/shared/components/AudioPreviewPlayer";
import { useScenarioMusic } from "../../hooks/useScenarioMusic";
import { useMusicGenerationJob } from "../../hooks/useMusicGenerationJob";
import { MoodSlotCardProps } from "./MoodSlotCard.types";

const DEFAULT_GENERATION_DURATION_SECONDS = 60;
const MIN_GENERATION_DURATION_SECONDS = 30;
const MAX_GENERATION_DURATION_SECONDS = 120;

export const MoodSlotCard: React.FC<MoodSlotCardProps> = ({
  scenarioId,
  mood,
  label,
  slot,
  quotaExceeded,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [prompt, setPrompt] = useState("");
  const [durationSeconds, setDurationSeconds] = useState(
    DEFAULT_GENERATION_DURATION_SECONDS,
  );
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    uploadTrack,
    isUploading,
    setDefaultTrack,
    requestGeneration,
    isRequestingGeneration,
    confirmGeneratedTrack,
    isConfirming,
    discardGenerationJob,
  } = useScenarioMusic(scenarioId);
  const { data: job } = useMusicGenerationJob(scenarioId, pendingJobId);
  const isBusy = isUploading || isRequestingGeneration || isConfirming;

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setErrorMessage(null);
    uploadTrack(
      { mood, file },
      { onError: () => setErrorMessage("Upload failed — please try again.") },
    );
  };

  const handleGenerateClick = () => {
    if (!prompt.trim()) return;
    setErrorMessage(null);
    requestGeneration(
      { mood, prompt, duration_seconds: durationSeconds },
      {
        onSuccess: (createdJob) => setPendingJobId(createdJob.job_id),
        onError: () => setErrorMessage("Music generation failed to start."),
      },
    );
  };

  const handleConfirm = () => {
    if (!pendingJobId) return;
    confirmGeneratedTrack(pendingJobId, {
      onSuccess: () => setPendingJobId(null),
      onError: () => setErrorMessage("Could not save the generated track."),
    });
  };

  const handleDiscard = () => {
    if (!pendingJobId) return;
    discardGenerationJob(pendingJobId);
    setPendingJobId(null);
    setPrompt("");
  };

  const sourceLabel =
    slot?.source === "upload"
      ? "Uploaded"
      : slot?.source === "generated"
        ? "Generated"
        : "Default track";

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-inset p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-content">{label}</h3>
        <span className="text-xs uppercase tracking-wide text-content-faint">
          {sourceLabel}
        </span>
      </div>

      {slot?.track_url && <AudioPreviewPlayer src={slot.track_url} />}

      <div className="flex flex-wrap gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/mpeg,audio/wav,audio/x-wav,audio/ogg"
          onChange={handleFileSelected}
          disabled={isBusy}
          className="hidden"
          aria-label={`Upload track for ${label}`}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={isBusy}
          onClick={() => fileInputRef.current?.click()}
        >
          {isUploading ? "Uploading…" : "Upload track"}
        </Button>
        {slot?.source !== "default" && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={isBusy}
            onClick={() => setDefaultTrack(mood)}
          >
            Use default
          </Button>
        )}
      </div>

      {!pendingJobId && (
        <div className="space-y-2 pt-2 border-t border-border-subtle">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
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
                min={MIN_GENERATION_DURATION_SECONDS}
                max={MAX_GENERATION_DURATION_SECONDS}
                value={durationSeconds}
                onChange={(e) => setDurationSeconds(Number(e.target.value))}
                disabled={isBusy || quotaExceeded}
                className="ml-2 w-16 rounded-md border border-border-subtle bg-surface px-1.5 py-1 text-xs text-content"
              />
            </label>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={isBusy || quotaExceeded || !prompt.trim()}
              onClick={handleGenerateClick}
            >
              {isRequestingGeneration ? "Submitting…" : "Generate with AI"}
            </Button>
          </div>
          {quotaExceeded && (
            <p className="text-xs text-content-faint">
              Generation quota reached for this scenario or today.
            </p>
          )}
        </div>
      )}

      {pendingJobId && job && (
        <div className="space-y-2 pt-2 border-t border-border-subtle">
          {(job.status === "pending" || job.status === "running") && (
            <p className="text-xs text-content-muted flex items-center gap-2">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-content-muted border-t-transparent" />
              Generating…
            </p>
          )}
          {job.status === "succeeded" && job.preview_url && (
            <>
              <AudioPreviewPlayer src={job.preview_url} />
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  disabled={isConfirming}
                  onClick={handleConfirm}
                >
                  {isConfirming ? "Saving…" : "Confirm"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleDiscard}
                >
                  Discard
                </Button>
              </div>
            </>
          )}
          {job.status === "failed" && (
            <>
              <p className="text-xs text-danger">
                {job.error_message || "Generation failed."}
              </p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleDiscard}
              >
                Dismiss
              </Button>
            </>
          )}
        </div>
      )}

      {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
    </div>
  );
};
