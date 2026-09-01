import React, { useState, useEffect } from "react";
import { SetupInputField } from "../../studio/stores/studio.store";

export interface PlaythroughSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  scenarioTitle: string;
  setupFields: SetupInputField[];
  onConfirm: (
    formattedPromptPayload: string,
    choices: Record<string, unknown>,
  ) => void;
}

export const PlaythroughSetupModal: React.FC<PlaythroughSetupModalProps> = ({
  isOpen,
  onClose,
  scenarioTitle,
  setupFields,
  onConfirm,
}) => {
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Initialize form defaults whenever setupFields change
  useEffect(() => {
    const initialValues: Record<string, any> = {};
    setupFields.forEach((field) => {
      if (field.defaultValue !== undefined) {
        initialValues[field.id] = field.defaultValue;
      } else if (field.type === "multi_select") {
        initialValues[field.id] = [];
      } else if (field.type === "single_select" && field.options.length > 0) {
        initialValues[field.id] = field.options[0].value;
      } else {
        initialValues[field.id] = "";
      }
    });
    setFormValues(initialValues);
    setErrors({});
  }, [setupFields]);

  if (!isOpen) return null;

  const handleChange = (fieldId: string, value: any) => {
    setFormValues((prev) => ({ ...prev, [fieldId]: value }));
    if (errors[fieldId]) {
      setErrors((prev) => {
        const copy = { ...prev };
        delete copy[fieldId];
        return copy;
      });
    }
  };

  const handleMultiSelectToggle = (fieldId: string, optionValue: string) => {
    const currentList: string[] = Array.isArray(formValues[fieldId])
      ? formValues[fieldId]
      : [];
    const exists = currentList.includes(optionValue);
    const updated = exists
      ? currentList.filter((v) => v !== optionValue)
      : [...currentList, optionValue];
    handleChange(fieldId, updated);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};

    setupFields.forEach((field) => {
      if (field.required) {
        const val = formValues[field.id];
        if (
          val === undefined ||
          val === "" ||
          (Array.isArray(val) && val.length === 0)
        ) {
          newErrors[field.id] =
            `Please select or enter a value for ${field.label}`;
        }
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Format choices into markdown payload for Gemini opening prompt
    const lines: string[] = ["\n[PLAYER CHARACTER SETUP]"];
    setupFields.forEach((field) => {
      const val = formValues[field.id];
      if (val === undefined || val === "") return;

      if (field.type === "single_select") {
        const matchedOption = field.options.find((o) => o.value === val);
        lines.push(
          `- ${field.label}: ${matchedOption ? matchedOption.label : val}`,
        );
      } else if (field.type === "multi_select") {
        const selectedLabels = (val as string[])
          .map((v) => field.options.find((o) => o.value === v)?.label || v)
          .join(", ");
        lines.push(`- ${field.label}: ${selectedLabels}`);
      } else {
        lines.push(`- ${field.label}: ${val}`);
      }
    });

    const formattedPayload = lines.join("\n");
    onConfirm(formattedPayload, formValues);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="w-full max-w-xl bg-zinc-950 border border-zinc-800 shadow-2xl p-6 md:p-8 space-y-6 font-sans text-zinc-100 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-zinc-800 pb-4">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
              Campaign Setup
            </span>
            <h2 className="text-xl font-serif font-bold text-zinc-100 mt-0.5">
              {scenarioTitle || "Initialize Adventure"}
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Customize your starting character and options before narration
              begins.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 transition-colors p-1"
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {setupFields.map((field) => (
            <div key={field.id} className="space-y-2">
              <label className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                {field.label}{" "}
                {field.required && <span className="text-red-400">*</span>}
              </label>

              {field.description && (
                <p className="text-xs text-zinc-500">{field.description}</p>
              )}

              {/* Input Renderers */}
              {field.type === "single_select" && (
                <select
                  value={formValues[field.id] || ""}
                  onChange={(e) => handleChange(field.id, e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500"
                >
                  <option value="">Select an option...</option>
                  {field.options.map((opt) => (
                    <option key={opt.id} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              )}

              {field.type === "multi_select" && (
                <div className="space-y-2 bg-zinc-900 border border-zinc-800 p-3">
                  {field.options.map((opt) => {
                    const isChecked = (formValues[field.id] || []).includes(
                      opt.value,
                    );
                    return (
                      <label
                        key={opt.id}
                        className="flex items-center gap-3 text-xs text-zinc-300 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() =>
                            handleMultiSelectToggle(field.id, opt.value)
                          }
                          className="accent-zinc-100"
                        />
                        {opt.label}
                      </label>
                    );
                  })}
                </div>
              )}

              {field.type === "text" && (
                <input
                  type="text"
                  value={formValues[field.id] || ""}
                  onChange={(e) => handleChange(field.id, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
                />
              )}

              {field.type === "textarea" && (
                <textarea
                  rows={3}
                  value={formValues[field.id] || ""}
                  onChange={(e) => handleChange(field.id, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500 resize-none"
                />
              )}

              {field.type === "number" && (
                <input
                  type="number"
                  value={formValues[field.id] || ""}
                  onChange={(e) => handleChange(field.id, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
                />
              )}

              {errors[field.id] && (
                <p className="text-xs text-red-400 mt-1">{errors[field.id]}</p>
              )}
            </div>
          ))}

          {/* Action Buttons */}
          <div className="pt-4 border-t border-zinc-900 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold uppercase tracking-wider border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-6 py-2 bg-zinc-100 hover:bg-white text-zinc-950 font-semibold text-xs uppercase tracking-wider transition-colors"
            >
              Start Playthrough
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
