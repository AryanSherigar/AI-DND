import React, { useEffect, useState } from "react";
import { useStudioStore } from "../../stores/studio.store";
import { DistractionFreeEditor } from "../MarkdownEditor/DistractionFreeEditor";

export const Step3Narrator: React.FC = () => {
  const { newbieDraft, updateNewbieDraft, setSaveState } = useStudioStore();
  const [localStyle, setLocalStyle] = useState(newbieDraft.narrativeStyle);
  const [localInstructions, setLocalInstructions] = useState(
    newbieDraft.aiInstructions,
  );

  // Sync external changes (e.g. from AI Assistant) into local editor
  useEffect(() => {
    setLocalStyle(newbieDraft.narrativeStyle);
  }, [newbieDraft.narrativeStyle]);

  useEffect(() => {
    setLocalInstructions(newbieDraft.aiInstructions);
  }, [newbieDraft.aiInstructions]);

  useEffect(() => {
    const handler = setTimeout(() => {
      if (
        localStyle !== newbieDraft.narrativeStyle ||
        localInstructions !== newbieDraft.aiInstructions
      ) {
        setSaveState(true);
        setTimeout(() => {
          updateNewbieDraft({
            narrativeStyle: localStyle,
            aiInstructions: localInstructions,
          });
          setSaveState(false, new Date());
        }, 500);
      }
    }, 1000);
    return () => clearTimeout(handler);
  }, [
    localStyle,
    localInstructions,
    newbieDraft,
    updateNewbieDraft,
    setSaveState,
  ]);

  return (
    <div className="space-y-8">
      <div className="space-y-2 border-b border-zinc-800 pb-4">
        <h2 className="text-2xl font-semibold text-zinc-100 tracking-tight">
          The Narrator
        </h2>
        <p className="text-sm text-zinc-400">
          Define the voice, tone, and strict rules for the AI narrator. Both are
          optional.
        </p>
      </div>

      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          Narrative Style & Vibe
        </label>
        <p className="text-xs text-zinc-500">
          Describe the writing style, tone, and genre flavor. E.g., "Gritty dark
          fantasy, descriptive combat, poetic language."
        </p>
        <DistractionFreeEditor
          value={localStyle}
          onChange={(val) => setLocalStyle(val)}
          placeholder="Write in the style of Tolkien..."
          className="h-48"
        />
      </div>

      <div className="space-y-3">
        <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          AI Instructions
        </label>
        <p className="text-xs text-zinc-500">
          Strict rules for the AI. E.g., "Never kill the player character
          without warning," "Do not speak for the player."
        </p>
        <DistractionFreeEditor
          value={localInstructions}
          onChange={(val) => setLocalInstructions(val)}
          placeholder="1. The AI must never..."
          className="h-48"
        />
      </div>
    </div>
  );
};
