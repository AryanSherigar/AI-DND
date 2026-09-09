import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStudioStore } from "../../stores/studio.store";
import { createScenario } from "../../api/scenarios.api";
import { PublishFlow } from "../PublishFlow/PublishFlow";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

export const Step4Review: React.FC = () => {
  const navigate = useNavigate();
  const { newbieDraft, setSaveState } = useStudioStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [draftScenarioId, setDraftScenarioId] = useState<string | null>(null);
  const [showPublishFlow, setShowPublishFlow] = useState(false);

  const createDraft = async () => {
    const response = await createScenario({
      title: newbieDraft.title.trim(),
      logline: newbieDraft.logline.trim() || undefined,
      mode: "newbie",
      complexity_tier: "newbie",
      player_count_support: newbieDraft.player_count_support || "solo",
      genre_tags: newbieDraft.genre_tags || [],
      estimated_playtime: newbieDraft.estimated_playtime || undefined,
      cover_image_url: newbieDraft.cover_image_url || undefined,
      narrator_persona:
        [newbieDraft.aiInstructions, newbieDraft.narrativeStyle]
          .filter(Boolean)
          .join("\n\n") || undefined,
      world_data: {
        // core-api maps this to memory-layer's required world_data.lore_text;
        // a creator using the single-lore-prompt toggle writes their lore into
        // singleLorePrompt instead, so worldLore alone would be empty and
        // publish would fail with "newbie mode requires world_data.lore_text".
        worldLore: newbieDraft.useSingleLorePrompt
          ? newbieDraft.singleLorePrompt
          : newbieDraft.worldLore,
        openingPrompt: newbieDraft.openingPrompt,
        mainConflict: newbieDraft.mainConflict,
        storyCards: newbieDraft.storyCards,
        singleLorePrompt: newbieDraft.singleLorePrompt,
      },
      setup_schema: newbieDraft.setupInputs || [],
    });
    return response;
  };

  const handleSaveDraft = async () => {
    if (!newbieDraft.title.trim()) {
      setErrorMsg("Scenario title is required.");
      return;
    }

    setErrorMsg(null);
    setIsSubmitting(true);
    setSaveState(true);

    try {
      const response = await createDraft();
      setSaveState(false, new Date());
      setIsSubmitting(false);
      navigate(`/setup/${response.scenario_id}`);
    } catch (err: unknown) {
      setIsSubmitting(false);
      setSaveState(false);
      setErrorMsg(
        extractErrorMessage(
          err,
          "Failed to save scenario. Please check your inputs.",
        ),
      );
    }
  };

  const handleStartPublish = async () => {
    if (!newbieDraft.title.trim()) {
      setErrorMsg("Scenario title is required.");
      return;
    }
    if (draftScenarioId) {
      setShowPublishFlow(true);
      return;
    }

    setErrorMsg(null);
    setIsSubmitting(true);
    setSaveState(true);

    try {
      const response = await createDraft();
      setSaveState(false, new Date());
      setIsSubmitting(false);
      setDraftScenarioId(response.scenario_id);
      setShowPublishFlow(true);
    } catch (err: unknown) {
      setIsSubmitting(false);
      setSaveState(false);
      setErrorMsg(
        extractErrorMessage(
          err,
          "Failed to save scenario. Please check your inputs.",
        ),
      );
    }
  };

  return (
    <div className="space-y-8 pb-32">
      <div className="space-y-2 border-b border-border-subtle pb-4">
        <h2 className="text-2xl font-semibold text-content tracking-tight">
          Review & Publish
        </h2>
        <p className="text-sm text-content-muted">
          Review your scenario details and player options before saving or
          publishing.
        </p>
      </div>

      {errorMsg && (
        <div className="rounded-md p-4 bg-danger/10 border border-danger/40 text-danger text-sm font-mono">
          {errorMsg}
        </div>
      )}

      {/* Configured Player Options Summary */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold tracking-wide text-content-muted uppercase border-b border-border-subtle pb-2">
          Player Setup Options ({newbieDraft.setupInputs?.length || 0})
        </h3>
        {!newbieDraft.setupInputs || newbieDraft.setupInputs.length === 0 ? (
          <p className="text-xs text-content-faint italic">
            No custom setup fields configured.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {newbieDraft.setupInputs.map((inputItem) => (
              <div
                key={inputItem.id}
                className="rounded-md bg-surface-inset border border-border-subtle p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-content">
                    {inputItem.label || "Untitled"}
                  </span>
                  <span className="rounded-md text-[10px] font-mono uppercase bg-surface border border-border-subtle px-2 py-0.5 text-content-muted">
                    {inputItem.type}
                  </span>
                </div>
                {inputItem.description && (
                  <p className="text-xs text-content-muted">
                    {inputItem.description}
                  </p>
                )}
                {inputItem.options && inputItem.options.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {inputItem.options.map((opt) => (
                      <span
                        key={opt.id}
                        className="rounded-md text-[11px] bg-surface border border-border-subtle text-content-muted px-2 py-0.5"
                      >
                        {opt.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="pt-8 flex justify-end gap-4">
        <button
          type="button"
          onClick={handleSaveDraft}
          disabled={isSubmitting}
          className="px-6 py-3 bg-surface hover:bg-surface-overlay text-content-muted font-semibold border border-border-subtle rounded-md transition-colors flex items-center gap-2 uppercase tracking-wider text-sm"
        >
          Save Draft
        </button>
        {!showPublishFlow && (
          <button
            type="button"
            onClick={handleStartPublish}
            disabled={isSubmitting}
            className="px-8 py-3 bg-content hover:bg-white text-surface font-semibold rounded-md transition-colors flex items-center gap-2 uppercase tracking-wider text-sm"
          >
            {isSubmitting ? (
              <>
                <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-surface"></span>
                Saving...
              </>
            ) : (
              "Publish Scenario"
            )}
          </button>
        )}
      </div>

      {showPublishFlow && (
        <PublishFlow
          scenarioId={draftScenarioId}
          onPublished={() => navigate(`/setup/${draftScenarioId}`)}
        />
      )}
    </div>
  );
};
