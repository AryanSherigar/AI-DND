import React, { useState } from "react";
import {
  useStudioStore,
  SetupInputField,
  SetupInputOption,
  SetupInputType,
} from "../../stores/studio.store";

export const StepPlayerSetup: React.FC = () => {
  const { newbieDraft, updateNewbieDraft } = useStudioStore();
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  const inputs = newbieDraft.setupInputs || [];

  const handleAddField = () => {
    const newId = String(Date.now());
    const newField: SetupInputField = {
      id: newId,
      key: `field_${inputs.length + 1}`,
      label: `Custom Option ${inputs.length + 1}`,
      type: "single_select",
      description: "",
      placeholder: "",
      required: false,
      options: [
        { id: `opt-${newId}-1`, label: "Option 1", value: "option_1" },
        { id: `opt-${newId}-2`, label: "Option 2", value: "option_2" },
      ],
      defaultValue: "option_1",
    };
    updateNewbieDraft({ setupInputs: [...inputs, newField] });
  };

  const handleUpdateField = (id: string, updates: Partial<SetupInputField>) => {
    const updated = inputs.map((item) =>
      item.id === id ? { ...item, ...updates } : item,
    );
    updateNewbieDraft({ setupInputs: updated });
  };

  const handleDeleteField = (id: string) => {
    updateNewbieDraft({ setupInputs: inputs.filter((item) => item.id !== id) });
  };

  const handleMoveField = (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= inputs.length) return;
    const reordered = [...inputs];
    const temp = reordered[index];
    reordered[index] = reordered[targetIndex];
    reordered[targetIndex] = temp;
    updateNewbieDraft({ setupInputs: reordered });
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-4">
        <div>
          <h2 className="text-2xl font-semibold text-content tracking-tight">
            Player Setup
          </h2>
          <p className="text-sm text-content-muted">
            Configure custom choices and inputs players must select before Turn
            1.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsPreviewOpen(!isPreviewOpen)}
            className="px-4 py-2 text-xs font-semibold uppercase tracking-wider border border-border-subtle bg-surface hover:bg-surface-overlay text-content-muted transition-colors rounded-md"
          >
            {isPreviewOpen ? "Edit Setup Fields" : "Live Player Preview"}
          </button>
          <button
            type="button"
            onClick={handleAddField}
            className="px-4 py-2 text-xs font-semibold uppercase tracking-wider bg-content text-surface hover:bg-white transition-colors rounded-md"
          >
            + Add Input Field
          </button>
        </div>
      </div>

      {/* Main Content: Preview Mode vs Config Mode */}
      {isPreviewOpen ? (
        <PlayerSetupPreview inputs={inputs} />
      ) : (
        <div className="space-y-6">
          {inputs.length === 0 ? (
            <div className="rounded-md p-8 border border-dashed border-border-subtle text-center space-y-3">
              <p className="text-sm text-content-faint">
                No custom setup options created yet.
              </p>
              <button
                type="button"
                onClick={handleAddField}
                className="px-4 py-2 text-xs uppercase tracking-wider bg-surface border border-border-subtle text-content-muted hover:bg-surface-overlay transition-colors rounded-md"
              >
                Create First Input
              </button>
            </div>
          ) : (
            inputs.map((fieldItem, index) => (
              <FieldEditorCard
                key={fieldItem.id}
                field={fieldItem}
                index={index}
                totalCount={inputs.length}
                onUpdate={(updates) => handleUpdateField(fieldItem.id, updates)}
                onDelete={() => handleDeleteField(fieldItem.id)}
                onMove={(direction) => handleMoveField(index, direction)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
};

interface FieldEditorCardProps {
  field: SetupInputField;
  index: number;
  totalCount: number;
  onUpdate: (updates: Partial<SetupInputField>) => void;
  onDelete: () => void;
  onMove: (direction: "up" | "down") => void;
}

const FieldEditorCard: React.FC<FieldEditorCardProps> = ({
  field,
  index,
  totalCount,
  onUpdate,
  onDelete,
  onMove,
}) => {
  const handleAddOption = () => {
    const optionId = `opt-${Date.now()}`;
    const newOptions: SetupInputOption[] = [
      ...field.options,
      {
        id: optionId,
        label: `Choice ${field.options.length + 1}`,
        value: `choice_${field.options.length + 1}`,
      },
    ];
    onUpdate({ options: newOptions });
  };

  const handleUpdateOption = (
    optionId: string,
    updates: Partial<SetupInputOption>,
  ) => {
    const updatedOptions = field.options.map((opt) =>
      opt.id === optionId ? { ...opt, ...updates } : opt,
    );
    onUpdate({ options: updatedOptions });
  };

  const handleDeleteOption = (optionId: string) => {
    const updatedOptions = field.options.filter((opt) => opt.id !== optionId);
    onUpdate({ options: updatedOptions });
  };

  return (
    <div className="border border-border-subtle bg-surface-inset p-6 space-y-6 rounded-md relative">
      {/* Top Card Controls */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-4">
        <div className="flex items-center gap-3">
          <span className="rounded-md font-mono text-xs text-content-faint uppercase px-2 py-1 bg-surface border border-border-subtle">
            #{index + 1}
          </span>
          <h3 className="text-sm font-semibold text-content tracking-wide">
            {field.label || "Untitled Field"}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={index === 0}
            onClick={() => onMove("up")}
            className="p-1.5 text-content-faint hover:text-content disabled:opacity-30 disabled:hover:text-content-faint"
            title="Move Up"
          >
            ↑
          </button>
          <button
            type="button"
            disabled={index === totalCount - 1}
            onClick={() => onMove("down")}
            className="p-1.5 text-content-faint hover:text-content disabled:opacity-30 disabled:hover:text-content-faint"
            title="Move Down"
          >
            ↓
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="px-2.5 py-1 text-xs text-danger hover:bg-danger/10/40 border border-danger/40/50 rounded-md transition-colors"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Field Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-content-muted uppercase tracking-wider">
            Field Label
          </label>
          <input
            type="text"
            value={field.label}
            onChange={(e) => onUpdate({ label: e.target.value })}
            placeholder="e.g., Character Class"
            className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content placeholder:text-content-faint focus:outline-none focus:border-border-strong"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold text-content-muted uppercase tracking-wider">
            Input Type
          </label>
          <select
            value={field.type}
            onChange={(e) =>
              onUpdate({ type: e.target.value as SetupInputType })
            }
            className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content focus:outline-none focus:border-border-strong"
          >
            <option value="single_select">
              Single Select (Dropdown/Radio)
            </option>
            <option value="multi_select">Multi Select (Checkboxes)</option>
            <option value="text">Short Text</option>
            <option value="textarea">Long Text / Backstory</option>
            <option value="number">Numeric Input</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-content-muted uppercase tracking-wider">
            Helper Description
          </label>
          <input
            type="text"
            value={field.description || ""}
            onChange={(e) => onUpdate({ description: e.target.value })}
            placeholder="Explain what this choice affects..."
            className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content placeholder:text-content-faint focus:outline-none focus:border-border-strong"
          />
        </div>

        <div className="flex items-end pb-2">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={field.required}
              onChange={(e) => onUpdate({ required: e.target.checked })}
              className="accent-amber-400 h-4 w-4"
            />
            <span className="text-xs font-semibold text-content-muted uppercase tracking-wider">
              Required Choice for Players
            </span>
          </label>
        </div>
      </div>

      {/* Conditional UI: Options list for single_select & multi_select */}
      {(field.type === "single_select" || field.type === "multi_select") && (
        <div className="space-y-4 border-t border-border-subtle pt-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-content-muted uppercase tracking-wider">
              Choices / Options
            </h4>
            <button
              type="button"
              onClick={handleAddOption}
              className="text-xs text-content-muted hover:text-content uppercase tracking-wider underline underline-offset-4"
            >
              + Add Choice
            </button>
          </div>

          <div className="space-y-2">
            {field.options.map((opt) => (
              <div key={opt.id} className="flex items-center gap-3">
                <input
                  type="text"
                  value={opt.label}
                  onChange={(e) =>
                    handleUpdateOption(opt.id, {
                      label: e.target.value,
                      value: e.target.value.toLowerCase().replace(/\s+/g, "_"),
                    })
                  }
                  placeholder="Choice Label"
                  className="rounded-md flex-1 bg-surface border border-border-subtle px-3 py-1.5 text-xs text-content focus:outline-none focus:border-border-strong"
                />
                <button
                  type="button"
                  onClick={() => handleDeleteOption(opt.id)}
                  className="text-content-faint hover:text-danger p-1"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conditional UI: Placeholder for text inputs */}
      {(field.type === "text" ||
        field.type === "textarea" ||
        field.type === "number") && (
        <div className="space-y-2 border-t border-border-subtle pt-4">
          <label className="block text-xs font-semibold text-content-muted uppercase tracking-wider">
            Placeholder Text
          </label>
          <input
            type="text"
            value={field.placeholder || ""}
            onChange={(e) => onUpdate({ placeholder: e.target.value })}
            placeholder="e.g. Enter character name..."
            className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content placeholder:text-content-faint focus:outline-none focus:border-border-strong"
          />
        </div>
      )}
    </div>
  );
};

interface PlayerSetupPreviewProps {
  inputs: SetupInputField[];
}

const PlayerSetupPreview: React.FC<PlayerSetupPreviewProps> = ({ inputs }) => {
  return (
    <div className="rounded-md border border-border-subtle bg-surface-inset p-8 space-y-6 max-w-2xl mx-auto shadow-2xl">
      <div className="border-b border-border-subtle pb-4">
        <span className="text-[10px] font-mono uppercase tracking-widest text-content-faint">
          Player View Simulation
        </span>
        <h3 className="text-xl font-serif text-content mt-1">
          Configure Your Playthrough
        </h3>
        <p className="text-xs text-content-muted">
          Select your initial options before beginning your adventure.
        </p>
      </div>

      {inputs.length === 0 ? (
        <p className="text-xs text-content-faint italic">
          No setup options configured.
        </p>
      ) : (
        <div className="space-y-6">
          {inputs.map((field) => (
            <div key={field.id} className="space-y-2">
              <label className="block text-xs font-semibold text-content-muted uppercase tracking-wider">
                {field.label}{" "}
                {field.required && <span className="text-danger">*</span>}
              </label>
              {field.description && (
                <p className="text-xs text-content-faint">
                  {field.description}
                </p>
              )}

              {field.type === "single_select" && (
                <select className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content focus:outline-none">
                  {field.options.map((opt) => (
                    <option key={opt.id} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              )}

              {field.type === "multi_select" && (
                <div className="rounded-md space-y-2 bg-surface border border-border-subtle p-3">
                  {field.options.map((opt) => (
                    <label
                      key={opt.id}
                      className="flex items-center gap-3 text-xs text-content-muted cursor-pointer"
                    >
                      <input type="checkbox" className="accent-amber-400" />
                      {opt.label}
                    </label>
                  ))}
                </div>
              )}

              {field.type === "text" && (
                <input
                  type="text"
                  placeholder={field.placeholder}
                  className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content placeholder:text-content-faint focus:outline-none"
                />
              )}

              {field.type === "textarea" && (
                <textarea
                  rows={3}
                  placeholder={field.placeholder}
                  className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content placeholder:text-content-faint focus:outline-none"
                />
              )}

              {field.type === "number" && (
                <input
                  type="number"
                  placeholder={field.placeholder}
                  className="rounded-md w-full bg-surface border border-border-subtle px-3 py-2 text-sm text-content placeholder:text-content-faint focus:outline-none"
                />
              )}
            </div>
          ))}
        </div>
      )}

      <div className="pt-4 border-t border-border-subtle flex justify-end">
        <button
          type="button"
          disabled
          className="px-6 py-2 bg-content text-surface font-semibold text-xs uppercase tracking-wider opacity-60 cursor-not-allowed"
        >
          Begin Adventure (Preview)
        </button>
      </div>
    </div>
  );
};
