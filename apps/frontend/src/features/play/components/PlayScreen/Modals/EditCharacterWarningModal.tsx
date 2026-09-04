import { useState } from "react";
import { usePlayStore } from "../../../stores/play.store";
import { CharacterSetupField } from "../../../types/play.types";
import { useUpdateCharacterFields } from "../../../hooks/useUpdateCharacterFields";

export function EditCharacterWarningModal() {
  const isOpen = usePlayStore((s) => s.is_warning_modal_open);
  const closeModal = usePlayStore((s) => s.closeWarningModal);
  const playthrough = usePlayStore((s) => s.playthrough);

  const [draftName, setDraftName] = useState(playthrough?.character_name ?? "");
  const [draftFields, setDraftFields] = useState<CharacterSetupField[]>(
    playthrough?.custom_fields ? [...playthrough.custom_fields] : [],
  );

  const updateCharacterFields = useUpdateCharacterFields(
    playthrough?.playthrough_id ?? "",
  );

  if (!isOpen || !playthrough) return null;

  const handleFieldChange = (key: string, value: string) => {
    setDraftFields((prev) =>
      prev.map((f) => (f.key === key ? { ...f, value } : f)),
    );
  };

  const handleSave = () => {
    const setupValues: Record<string, string> = {
      character_name: draftName,
      ...Object.fromEntries(draftFields.map((f) => [f.key, f.value])),
    };
    updateCharacterFields.mutate(setupValues, { onSuccess: closeModal });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-stone-950 border border-amber-900/40 rounded-2xl p-6 shadow-2xl space-y-5 animate-scale-up">
        {/* Warning Banner */}
        <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/40 flex items-start gap-3">
          <svg
            className="w-5 h-5 text-amber-400 shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <div className="space-y-1">
            <h4 className="font-mono text-xs uppercase text-amber-300 font-bold">
              Immersion Notice
            </h4>
            <p className="font-serif text-xs text-amber-200/80 leading-relaxed">
              Modifying character background details during an ongoing
              playthrough can reduce story immersion and cause mild narrative
              inconsistencies with past AI turns.
            </p>
          </div>
        </div>

        {/* Editable Fields */}
        <div className="space-y-3">
          <h4 className="font-mono text-xs uppercase text-amber-400/90 tracking-wider">
            Edit Character Choices
          </h4>
          <div className="space-y-1">
            <label className="font-mono text-xs text-stone-400 block">
              Character Name
            </label>
            <input
              type="text"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              className="w-full bg-stone-900 text-amber-100 font-serif text-sm p-2.5 rounded border border-amber-900/30 focus:border-amber-500 focus:outline-none"
            />
          </div>
          {draftFields.map((field) => (
            <div key={field.key} className="space-y-1">
              <label className="font-mono text-xs text-stone-400 block">
                {field.label}
              </label>
              <input
                type="text"
                value={field.value}
                onChange={(e) => handleFieldChange(field.key, e.target.value)}
                className="w-full bg-stone-900 text-amber-100 font-serif text-sm p-2.5 rounded border border-amber-900/30 focus:border-amber-500 focus:outline-none"
              />
            </div>
          ))}
        </div>

        {updateCharacterFields.isError && (
          <p className="font-mono text-xs text-red-400">
            Failed to save changes. Please try again.
          </p>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2 border-t border-amber-900/20">
          <button
            type="button"
            onClick={closeModal}
            className="px-4 py-2 bg-stone-900 hover:bg-stone-800 text-stone-300 font-mono text-xs rounded border border-stone-700 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={updateCharacterFields.isPending}
            onClick={handleSave}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-stone-950 font-mono text-xs font-bold rounded transition-colors cursor-pointer"
          >
            {updateCharacterFields.isPending ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
