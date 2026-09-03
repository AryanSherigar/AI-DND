import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";

export interface NormalizedSetupField {
  id: string;
  key: string;
  label: string;
  type: string;
  description?: string;
  placeholder?: string;
  required?: boolean;
  options: Array<{ id: string; label: string; value: string }>;
  defaultValue?: any;
}

interface SetupStageCardProps {
  scenario: any;
  isSubmitting?: boolean;
  onSubmit: (
    formattedPayload: string,
    formValues: Record<string, unknown>,
  ) => void;
}

export const SetupStageCard: React.FC<SetupStageCardProps> = ({
  scenario,
  isSubmitting = false,
  onSubmit,
}) => {
  const rawFields: any[] = scenario.setup_schema || scenario.setupInputs || [];

  const setupFields: NormalizedSetupField[] = rawFields.map((f, index) => {
    const fieldKey = f.key || f.field_key || f.id || `field_${index}`;
    const rawOptions = f.options || [];
    const options = rawOptions.map((opt: any, optIndex: number) => {
      if (typeof opt === "string") {
        return { id: `opt-${optIndex}`, label: opt, value: opt };
      }
      return {
        id: opt.id || `opt-${optIndex}`,
        label: opt.label || opt.value || `Option ${optIndex + 1}`,
        value: opt.value ?? opt.label ?? "",
      };
    });

    return {
      id: fieldKey,
      key: fieldKey,
      label: f.label || fieldKey,
      type: f.type || "text",
      description: f.description || "",
      placeholder: f.placeholder || "",
      required: Boolean(f.required),
      options,
      defaultValue: f.defaultValue,
    };
  });

  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const initialValues: Record<string, any> = {};
    setupFields.forEach((field) => {
      if (field.defaultValue !== undefined) {
        initialValues[field.key] = field.defaultValue;
      } else if (field.type === "multi_select") {
        initialValues[field.key] = [];
      } else if (
        (field.type === "single_select" || field.type === "select") &&
        field.options.length > 0
      ) {
        initialValues[field.key] = field.options[0].value;
      } else {
        initialValues[field.key] = "";
      }
    });
    setFormValues(initialValues);
    setErrors({});
  }, [scenario.id, scenario.scenario_id]);

  const handleChange = (fieldKey: string, value: any) => {
    setFormValues((prev) => ({ ...prev, [fieldKey]: value }));
    if (errors[fieldKey]) {
      setErrors((prev) => {
        const copy = { ...prev };
        delete copy[fieldKey];
        return copy;
      });
    }
  };

  const handleMultiSelectToggle = (fieldKey: string, optionValue: string) => {
    const currentList: string[] = Array.isArray(formValues[fieldKey])
      ? formValues[fieldKey]
      : [];
    const exists = currentList.includes(optionValue);
    const updated = exists
      ? currentList.filter((v) => v !== optionValue)
      : [...currentList, optionValue];
    handleChange(fieldKey, updated);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};

    setupFields.forEach((field) => {
      if (field.required) {
        const val = formValues[field.key];
        if (
          val === undefined ||
          val === "" ||
          (Array.isArray(val) && val.length === 0)
        ) {
          newErrors[field.key] = `Selection required for ${field.label}`;
        }
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const lines: string[] = ["\n[PLAYER CHARACTER SETUP]"];
    setupFields.forEach((field) => {
      const val = formValues[field.key];
      if (val === undefined || val === "") return;

      if (field.type === "single_select" || field.type === "select") {
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
    onSubmit(formattedPayload, formValues);
  };

  return (
    <div className="w-full max-w-xl md:max-w-2xl bg-zinc-950/85 backdrop-blur-xl border border-zinc-800/80 shadow-[0_0_50px_rgba(0,0,0,0.8)] p-6 sm:p-10 rounded-2xl relative z-10 space-y-8">
      {/* Top Accent Bar */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-[2px] bg-gradient-to-r from-transparent via-amber-500/60 to-transparent" />

      {/* Header */}
      <div className="text-center space-y-3 pb-6 border-b border-zinc-800/60">
        <div className="flex items-center justify-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-amber-500/90 bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
            CAMPAIGN INITIATION
          </span>
        </div>

        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-zinc-100 tracking-wide">
          {scenario.title}
        </h1>

        <p className="font-mono text-xs text-zinc-400 max-w-md mx-auto">
          Craft your starting parameters before the AI Narrator weaves your
          fate.
        </p>
      </div>

      {/* Form Content */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {setupFields.length === 0 ? (
          <div className="text-center py-8 px-4 bg-zinc-900/40 border border-zinc-800/50 rounded-xl space-y-3">
            <div className="w-10 h-10 mx-auto rounded-full bg-zinc-800/60 flex items-center justify-center text-amber-400/80">
              <svg
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
            </div>
            <p className="font-serif text-sm text-zinc-300 italic">
              No character customization is required for this scenario.
            </p>
            <p className="font-mono text-xs text-zinc-500">
              The chronicle begins immediately upon departure.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {setupFields.map((field) => (
              <div key={field.key} className="space-y-2 group">
                <label className="block font-mono text-xs uppercase tracking-wider text-zinc-300 font-semibold group-focus-within:text-amber-400 transition-colors">
                  {field.label}{" "}
                  {field.required && (
                    <span className="text-amber-500 font-bold">*</span>
                  )}
                </label>

                {field.description && (
                  <p className="font-sans text-xs text-zinc-400">
                    {field.description}
                  </p>
                )}

                {(field.type === "single_select" ||
                  field.type === "select") && (
                  <div className="relative">
                    <select
                      value={formValues[field.key] || ""}
                      onChange={(e) => handleChange(field.key, e.target.value)}
                      className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg appearance-none focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all cursor-pointer"
                    >
                      <option value="" disabled>
                        Select option...
                      </option>
                      {field.options.map((opt) => (
                        <option key={opt.id} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-zinc-500">
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </div>
                  </div>
                )}

                {field.type === "multi_select" && (
                  <div className="space-y-2 bg-zinc-900/60 border border-zinc-800/80 p-4 rounded-lg">
                    {field.options.map((opt) => {
                      const isChecked = (formValues[field.key] || []).includes(
                        opt.value,
                      );
                      return (
                        <label
                          key={opt.id}
                          className="flex items-center gap-3 text-xs font-mono text-zinc-300 cursor-pointer hover:text-zinc-100 transition-colors py-1"
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() =>
                              handleMultiSelectToggle(field.key, opt.value)
                            }
                            className="w-4 h-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500/40 accent-amber-500"
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
                    value={formValues[field.key] || ""}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    placeholder={field.placeholder || "Enter text..."}
                    className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all"
                  />
                )}

                {field.type === "textarea" && (
                  <textarea
                    rows={3}
                    value={formValues[field.key] || ""}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    placeholder={field.placeholder || "Enter details..."}
                    className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all resize-none"
                  />
                )}

                {field.type === "number" && (
                  <input
                    type="number"
                    value={formValues[field.key] || ""}
                    onChange={(e) =>
                      handleChange(
                        field.key,
                        e.target.valueAsNumber || e.target.value,
                      )
                    }
                    placeholder={field.placeholder}
                    className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all"
                  />
                )}

                {errors[field.key] && (
                  <p className="font-mono text-xs text-red-400 mt-1 flex items-center gap-1">
                    <span>⚠</span> {errors[field.key]}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Action Controls */}
        <div className="pt-6 border-t border-zinc-800/80 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Link
            to="/discover"
            className="w-full sm:w-auto px-5 py-3 font-mono text-xs uppercase tracking-wider text-zinc-400 hover:text-zinc-200 transition-colors text-center"
          >
            ← Back to Discover
          </Link>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full sm:w-auto px-8 py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-zinc-950 font-serif font-bold text-sm tracking-wider uppercase rounded-lg shadow-[0_0_25px_rgba(245,158,11,0.3)] hover:shadow-[0_0_35px_rgba(245,158,11,0.5)] transition-all flex items-center justify-center gap-2 group cursor-pointer"
          >
            <span>{isSubmitting ? "Initiating..." : "Embark on Journey"}</span>
            <svg
              className="w-4 h-4 transform group-hover:translate-x-1 transition-transform"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
};
