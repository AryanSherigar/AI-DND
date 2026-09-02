import React, { useState } from "react";
import { usePublish } from "../../hooks/usePublish";
import { updateScenarioContentTag } from "../../api/scenarios.api";
import { ContentTagPicker } from "./ContentTagPicker";
import { ContentTag } from "@/shared/constants/content-tags";

export interface PublishFlowProps {
  scenarioId: string | null;
  onPublished?: () => void;
}

export const PublishFlow: React.FC<PublishFlowProps> = ({
  scenarioId,
  onPublished,
}) => {
  const [contentTag, setContentTag] = useState<ContentTag | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isTaggingContent, setIsTaggingContent] = useState(false);

  const {
    status,
    isTriggering,
    isPolling,
    triggerError,
    publishError,
    publish,
  } = usePublish(scenarioId);

  const isBusy = isTaggingContent || isTriggering || isPolling;
  const errorMessage = validationError || triggerError || publishError;

  React.useEffect(() => {
    if (status === "published") {
      onPublished?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const handlePublish = async () => {
    setValidationError(null);
    if (!scenarioId) {
      setValidationError("Save the scenario as a draft before publishing.");
      return;
    }
    if (!contentTag) {
      setValidationError("Select a content tag before publishing.");
      return;
    }

    setIsTaggingContent(true);
    try {
      await updateScenarioContentTag(scenarioId, contentTag);
    } catch (err: any) {
      setValidationError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to save content tag.",
      );
      return;
    } finally {
      setIsTaggingContent(false);
    }

    publish();
  };

  const buttonLabel = () => {
    if (isTaggingContent) return "Saving Content Tag...";
    if (isTriggering) return "Starting...";
    if (isPolling) return "Publishing...";
    if (status === "published") return "Re-Publish";
    if (status === "publish_failed" || status === "draft") {
      return errorMessage ? "Retry Publish" : "Publish Scenario";
    }
    return "Publish Scenario";
  };

  return (
    <div className="space-y-6 border-t border-zinc-800 pt-8">
      <ContentTagPicker
        value={contentTag}
        onChange={setContentTag}
        disabled={isBusy}
      />

      {errorMessage && (
        <div className="p-4 bg-red-950/50 border border-red-800 text-red-200 text-sm font-mono">
          {errorMessage}
        </div>
      )}

      {status === "published" && !errorMessage && (
        <div className="p-4 bg-emerald-950/50 border border-emerald-800 text-emerald-200 text-sm font-mono">
          Scenario published — it is now live in discovery.
        </div>
      )}

      <button
        type="button"
        onClick={handlePublish}
        disabled={isBusy}
        className="px-8 py-3 bg-zinc-100 hover:bg-white text-zinc-950 font-semibold rounded-none transition-colors flex items-center gap-2 uppercase tracking-wider text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isBusy && (
          <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-zinc-950" />
        )}
        {buttonLabel()}
      </button>
    </div>
  );
};
