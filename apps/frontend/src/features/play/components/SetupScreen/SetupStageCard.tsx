import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  NormalizedSetupField,
  SetupScenarioData,
  SetupStageCardProps,
} from "./SetupStageCard.types";
import {
  getArrayValue,
  getInitialFormValues,
  getScenarioIdentifier,
  normalizeSetupFields,
  validateSetupForm,
  formatSetupSummary,
} from "./setupStageUtils";
import { SetupFieldRenderer } from "./SetupFieldRenderer";
import { SetupStageHeader } from "./SetupStageHeader";
import { SetupStageEmptyState } from "./SetupStageEmptyState";

export type { NormalizedSetupField, SetupScenarioData, SetupStageCardProps };

export const SetupStageCard: React.FC<SetupStageCardProps> = ({
  scenario,
  isSubmitting = false,
  onSubmit,
}) => {
  const setupFields = useMemo(() => normalizeSetupFields(scenario), [scenario]);
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const scenarioIdentifier = getScenarioIdentifier(scenario);

  useEffect(() => {
    setFormValues(getInitialFormValues(setupFields));
    setErrors({});
  }, [scenarioIdentifier, setupFields]);

  const handleChange = (fieldKey: string, value: unknown): void => {
    setFormValues((prev) => ({ ...prev, [fieldKey]: value }));
    if (errors[fieldKey]) {
      setErrors((prev) => {
        const copy = { ...prev };
        delete copy[fieldKey];
        return copy;
      });
    }
  };

  const handleMultiSelectToggle = (
    fieldKey: string,
    optionValue: string,
  ): void => {
    const currentList = getArrayValue(formValues[fieldKey]);
    const exists = currentList.includes(optionValue);
    const updated = exists
      ? currentList.filter((v) => v !== optionValue)
      : [...currentList, optionValue];
    handleChange(fieldKey, updated);
  };

  const handleSubmit = (e: React.FormEvent): void => {
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

      <SetupStageHeader title={scenario.title} />

      <form onSubmit={handleSubmit} className="space-y-6">
        {setupFields.length === 0 ? (
          <SetupStageEmptyState />
        ) : (
          <div className="space-y-6">
            {setupFields.map((field) => (
              <SetupFieldRenderer
                key={field.key}
                field={field}
                value={formValues[field.key]}
                error={errors[field.key]}
                onChange={handleChange}
                onMultiSelectToggle={handleMultiSelectToggle}
              />
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
