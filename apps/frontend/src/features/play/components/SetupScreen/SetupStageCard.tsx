import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { ScenarioDetailResponse, ScenarioMock } from "../../types/scenario";

export interface NormalizedSetupField {
  id: string;
  key: string;
  label: string;
  type: string;
  description?: string;
  placeholder?: string;
  required?: boolean;
  options: Array<{ id: string; label: string; value: string }>;
  defaultValue?: unknown;
  is_character_name?: boolean;
  predicate?: string;
}

export type SetupScenarioData =
  | ScenarioDetailResponse
  | ScenarioMock
  | {
      id?: string;
      scenario_id?: string;
      title?: string;
      setup_schema?: unknown[];
      setupInputs?: unknown[];
    };

interface SetupStageCardProps {
  scenario: SetupScenarioData;
  isSubmitting?: boolean;
  onSubmit: (
    formattedPayload: string,
    formValues: Record<string, unknown>,
  ) => void;
}

const getStringValue = (val: unknown): string => {
  if (typeof val === "string" || typeof val === "number") {
    return String(val);
  }
  return "";
};

const getArrayValue = (val: unknown): string[] => {
  if (Array.isArray(val)) {
    return val.filter((item): item is string => typeof item === "string");
  }
  return [];
};

const normalizeOptions = (
  rawOptions: unknown[],
): Array<{ id: string; label: string; value: string }> => {
  return rawOptions.map((opt, optIndex) => {
    if (typeof opt === "string") {
      return { id: `opt-${optIndex}`, label: opt, value: opt };
    }
    const optRecord = (opt && typeof opt === "object" ? opt : {}) as Record<
      string,
      unknown
    >;
    const optLabel = String(
      optRecord.label || optRecord.value || `Option ${optIndex + 1}`,
    );
    const optValue = String(optRecord.value ?? optRecord.label ?? "");
    const optId = String(optRecord.id || `opt-${optIndex}`);
    return { id: optId, label: optLabel, value: optValue };
  });
};

const normalizeField = (
  f: Record<string, unknown>,
  index: number,
): NormalizedSetupField => {
  const fieldKey = String(f.key || f.field_key || f.id || `field_${index}`);
  const rawOptions = Array.isArray(f.options) ? f.options : [];
  const options = normalizeOptions(rawOptions);
  const isCharacterName = Boolean(
    f.is_character_name || fieldKey === "character_name" || fieldKey === "name",
  );
  return {
    id: fieldKey,
    key: fieldKey,
    label: String(f.label || fieldKey),
    type: String(f.type || "text"),
    description: String(f.description || ""),
    placeholder:
      String(f.placeholder || "") ||
      (isCharacterName ? "Enter your character name..." : ""),
    required: Boolean(f.required) || isCharacterName,
    options,
    defaultValue: f.defaultValue,
    is_character_name: isCharacterName,
    predicate: f.predicate ? String(f.predicate) : undefined,
  };
};

const normalizeSetupFields = (
  scenario: SetupScenarioData,
): NormalizedSetupField[] => {
  const schema =
    "setup_schema" in scenario && scenario.setup_schema
      ? scenario.setup_schema
      : "setupInputs" in scenario && scenario.setupInputs
        ? scenario.setupInputs
        : [];
  const rawFields = Array.isArray(schema) ? schema : [];
  return rawFields
    .filter(
      (f): f is Record<string, unknown> => typeof f === "object" && f !== null,
    )
    .map((f, index) => normalizeField(f, index));
};

const getInitialFormValues = (
  fields: NormalizedSetupField[],
): Record<string, unknown> => {
  const initialValues: Record<string, unknown> = {};
  fields.forEach((field) => {
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
  return initialValues;
};

const validateSetupForm = (
  fields: NormalizedSetupField[],
  formValues: Record<string, unknown>,
): Record<string, string> => {
  const errors: Record<string, string> = {};
  fields.forEach((field) => {
    if (!field.required) return;
    const val = formValues[field.key];
    if (
      val === undefined ||
      val === "" ||
      (Array.isArray(val) && val.length === 0)
    ) {
      errors[field.key] = `Selection required for ${field.label}`;
    }
  });
  return errors;
};

const formatSetupSummary = (
  fields: NormalizedSetupField[],
  formValues: Record<string, unknown>,
): string => {
  const lines: string[] = ["\n[PLAYER CHARACTER SETUP]"];
  fields.forEach((field) => {
    const val = formValues[field.key];
    if (val === undefined || val === "") return;

    if (field.type === "single_select" || field.type === "select") {
      const matched = field.options.find((o) => o.value === val);
      lines.push(`- ${field.label}: ${matched ? matched.label : String(val)}`);
    } else if (field.type === "multi_select") {
      const arr = getArrayValue(val);
      const labels = arr
        .map((v) => field.options.find((o) => o.value === v)?.label || v)
        .join(", ");
      lines.push(`- ${field.label}: ${labels}`);
    } else {
      lines.push(`- ${field.label}: ${String(val)}`);
    }
  });
  return lines.join("\n");
};

export const SetupStageCard: React.FC<SetupStageCardProps> = ({
  scenario,
  isSubmitting = false,
  onSubmit,
}) => {
  const setupFields = useMemo(() => normalizeSetupFields(scenario), [scenario]);

  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const scenarioIdentifier =
    "id" in scenario && scenario.id
      ? scenario.id
      : "scenario_id" in scenario && scenario.scenario_id
        ? scenario.scenario_id
        : "";

  useEffect(() => {
    setFormValues(getInitialFormValues(setupFields));
    setErrors({});
  }, [scenarioIdentifier, setupFields]);

  const handleChange = (fieldKey: string, value: unknown) => {
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
    const currentList = getArrayValue(formValues[fieldKey]);
    const exists = currentList.includes(optionValue);
    const updated = exists
      ? currentList.filter((v) => v !== optionValue)
      : [...currentList, optionValue];
    handleChange(fieldKey, updated);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors = validateSetupForm(setupFields, formValues);
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    const formattedPayload = formatSetupSummary(setupFields, formValues);
    onSubmit(formattedPayload, formValues);
  };

  return (
    <div className="w-full max-w-xl md:max-w-2xl bg-zinc-950/85 backdrop-blur-xl border border-zinc-800/80 shadow-[0_0_50px_rgba(0,0,0,0.8)] p-6 sm:p-10 rounded-2xl relative z-10 space-y-8">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-[2px] bg-gradient-to-r from-transparent via-amber-500/60 to-transparent" />

      <div className="text-center space-y-3 pb-6 border-b border-zinc-800/60">
        <div className="flex items-center justify-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-amber-500/90 bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
            CAMPAIGN INITIATION
          </span>
        </div>

        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-zinc-100 tracking-wide">
          {scenario.title || "Scenario Setup"}
        </h1>

        <p className="font-mono text-xs text-zinc-400 max-w-md mx-auto">
          Craft your starting parameters before the AI Narrator weaves your
          fate.
        </p>
      </div>

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
                  {field.is_character_name && (
                    <span className="text-[10px] text-amber-500/80 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 ml-1">
                      PROTAGONIST
                    </span>
                  )}
                  {field.required && (
                    <span className="text-amber-500 font-bold ml-1">*</span>
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
                      value={getStringValue(formValues[field.key])}
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
                      const isChecked = getArrayValue(
                        formValues[field.key],
                      ).includes(opt.value);
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
                    value={getStringValue(formValues[field.key])}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    placeholder={field.placeholder || "Enter text..."}
                    className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all"
                  />
                )}

                {field.type === "textarea" && (
                  <textarea
                    rows={3}
                    value={getStringValue(formValues[field.key])}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    placeholder={field.placeholder || "Enter details..."}
                    className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all resize-none"
                  />
                )}

                {field.type === "number" && (
                  <input
                    type="number"
                    value={getStringValue(formValues[field.key])}
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
