import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStudioStore } from "../../stores/studio.store";
import { createScenario } from "../../api/scenarios.api";
import { PublishFlow } from "../PublishFlow/PublishFlow";

// Initial editable entities & facts
const INITIAL_ENTITIES = [
  {
    id: 1,
    name: "The Crimson Guild",
    type: "Faction",
    desc: "Ruthless mercenaries seeking ancient artifacts.",
  },
  {
    id: 2,
    name: "Elara",
    type: "Character",
    desc: "A scholar holding forgotten magic.",
  },
];

const INITIAL_FACTS = [
  { id: 1, text: "The Crimson Guild is hunting ancient relics." },
  { id: 2, text: "The subterranean ruins are sealed by draconic runes." },
];

export const Step4Review: React.FC = () => {
  const navigate = useNavigate();
  const { newbieDraft, setSaveState } = useStudioStore();
  const [entities, setEntities] = useState(INITIAL_ENTITIES);
  const [facts, setFacts] = useState(INITIAL_FACTS);
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
        worldLore: newbieDraft.worldLore,
        openingPrompt: newbieDraft.openingPrompt,
        mainConflict: newbieDraft.mainConflict,
        storyCards: newbieDraft.storyCards,
        singleLorePrompt: newbieDraft.singleLorePrompt,
        entities,
        facts,
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
    } catch (err: any) {
      setIsSubmitting(false);
      setSaveState(false);
      setErrorMsg(
        err.response?.data?.detail ||
          err.message ||
          "Failed to save scenario. Please check your inputs.",
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
    } catch (err: any) {
      setIsSubmitting(false);
      setSaveState(false);
      setErrorMsg(
        err.response?.data?.detail ||
          err.message ||
          "Failed to save scenario. Please check your inputs.",
      );
    }
  };

  return (
    <div className="space-y-8 pb-32">
      <div className="space-y-2 border-b border-zinc-800 pb-4">
        <h2 className="text-2xl font-semibold text-zinc-100 tracking-tight">
          Review & Publish
        </h2>
        <p className="text-sm text-zinc-400">
          Review your scenario details, player options, entities, and facts
          before saving or publishing.
        </p>
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-950/50 border border-red-800 text-red-200 text-sm font-mono">
          {errorMsg}
        </div>
      )}

      {/* Configured Player Options Summary */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase border-b border-zinc-800 pb-2">
          Player Setup Options ({newbieDraft.setupInputs?.length || 0})
        </h3>
        {!newbieDraft.setupInputs || newbieDraft.setupInputs.length === 0 ? (
          <p className="text-xs text-zinc-500 italic">
            No custom setup fields configured.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {newbieDraft.setupInputs.map((inputItem) => (
              <div
                key={inputItem.id}
                className="bg-zinc-950 border border-zinc-800 p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-zinc-100">
                    {inputItem.label || "Untitled"}
                  </span>
                  <span className="text-[10px] font-mono uppercase bg-zinc-900 border border-zinc-800 px-2 py-0.5 text-zinc-400">
                    {inputItem.type}
                  </span>
                </div>
                {inputItem.description && (
                  <p className="text-xs text-zinc-400">
                    {inputItem.description}
                  </p>
                )}
                {inputItem.options && inputItem.options.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {inputItem.options.map((opt) => (
                      <span
                        key={opt.id}
                        className="text-[11px] bg-zinc-900 border border-zinc-800 text-zinc-300 px-2 py-0.5"
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

      {/* Extracted Entities */}
      <div className="space-y-6">
        <h3 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase border-b border-zinc-800 pb-2">
          Extracted Entities
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {entities.map((e) => (
            <div
              key={e.id}
              className="bg-zinc-950 border border-zinc-800 p-4 space-y-3"
            >
              <div className="flex gap-2">
                <input
                  type="text"
                  value={e.name}
                  onChange={(ev) =>
                    setEntities(
                      entities.map((en) =>
                        en.id === e.id ? { ...en, name: ev.target.value } : en,
                      ),
                    )
                  }
                  className="flex-1 bg-transparent border-b border-zinc-800 rounded-none px-2 py-1 text-sm font-semibold text-zinc-100 focus:outline-none focus:border-zinc-400"
                />
                <input
                  type="text"
                  value={e.type}
                  onChange={(ev) =>
                    setEntities(
                      entities.map((en) =>
                        en.id === e.id ? { ...en, type: ev.target.value } : en,
                      ),
                    )
                  }
                  className="w-24 bg-transparent border-b border-zinc-800 rounded-none px-2 py-1 text-xs font-semibold uppercase tracking-wider text-zinc-400 focus:outline-none focus:border-zinc-400 text-center"
                />
              </div>
              <textarea
                value={e.desc}
                onChange={(ev) =>
                  setEntities(
                    entities.map((en) =>
                      en.id === e.id ? { ...en, desc: ev.target.value } : en,
                    ),
                  )
                }
                className="w-full h-16 bg-zinc-900 border border-zinc-800 rounded-none px-3 py-2 text-sm font-sans text-zinc-300 focus:outline-none focus:border-zinc-400 resize-none"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Extracted Facts */}
      <div className="space-y-6">
        <h3 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase border-b border-zinc-800 pb-2">
          Extracted Facts
        </h3>
        <div className="space-y-3">
          {facts.map((f) => (
            <div key={f.id} className="bg-zinc-950 border border-zinc-800 p-3">
              <input
                type="text"
                value={f.text}
                onChange={(ev) =>
                  setFacts(
                    facts.map((fa) =>
                      fa.id === f.id ? { ...fa, text: ev.target.value } : fa,
                    ),
                  )
                }
                className="w-full bg-transparent rounded-none px-3 py-1 text-sm font-sans text-zinc-300 focus:outline-none focus:border-b focus:border-zinc-400"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="pt-8 flex justify-end gap-4">
        <button
          type="button"
          onClick={handleSaveDraft}
          disabled={isSubmitting}
          className="px-6 py-3 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-semibold border border-zinc-700 rounded-none transition-colors flex items-center gap-2 uppercase tracking-wider text-sm"
        >
          Save Draft
        </button>
        {!showPublishFlow && (
          <button
            type="button"
            onClick={handleStartPublish}
            disabled={isSubmitting}
            className="px-8 py-3 bg-zinc-100 hover:bg-white text-zinc-950 font-semibold rounded-none transition-colors flex items-center gap-2 uppercase tracking-wider text-sm"
          >
            {isSubmitting ? (
              <>
                <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-zinc-950"></span>
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
