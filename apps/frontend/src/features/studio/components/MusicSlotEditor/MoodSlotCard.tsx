import React, { useState } from "react";
import { AudioPreviewPlayer } from "@/shared/components/AudioPreviewPlayer";
import { useScenarioMusic } from "../../hooks/useScenarioMusic";
import { useMusicGenerationJob } from "../../hooks/useMusicGenerationJob";
import { MoodSlotCardProps } from "./MoodSlotCard.types";
import { MoodSlotUploadRow } from "./MoodSlotUploadRow";
import { MoodSlotPromptForm } from "./MoodSlotPromptForm";
import { MoodSlotJobStatus } from "./MoodSlotJobStatus";

const DEFAULT_GENERATION_DURATION_SECONDS = 60;

const getSourceLabel = (source?: string): string => {
  if (source === "upload") return "Uploaded";
  if (source === "generated") return "Generated";
  return "Default track";
};

export const MoodSlotCard: React.FC<MoodSlotCardProps> = ({
  scenarioId,
  mood,
  label,
  slot,
  quotaExceeded,
}) => {
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

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-inset p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-content">{label}</h3>
        <span className="text-xs uppercase tracking-wide text-content-faint">
          {getSourceLabel(slot?.source)}
        </span>
      </div>

      {slot?.track_url && <AudioPreviewPlayer src={slot.track_url} />}

      <MoodSlotUploadRow
        label={label}
        isBusy={isBusy}
        isUploading={isUploading}
        isCustomTrack={slot?.source !== "default"}
        onFileSelect={handleFileSelected}
        onUseDefault={() => setDefaultTrack(mood)}
      />

      {!pendingJobId && (
        <MoodSlotPromptForm
          prompt={prompt}
          onPromptChange={setPrompt}
          durationSeconds={durationSeconds}
          onDurationChange={setDurationSeconds}
          isBusy={isBusy}
          quotaExceeded={quotaExceeded}
          isRequesting={isRequestingGeneration}
          onGenerate={handleGenerateClick}
        />
      )}

      {pendingJobId && job && (
        <MoodSlotJobStatus
          job={job}
          isConfirming={isConfirming}
          onConfirm={handleConfirm}
          onDiscard={handleDiscard}
        />
      )}

      {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
    </div>
  );
};
