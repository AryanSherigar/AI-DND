import React from "react";
import { SetupInputField } from "@/shared/types/scenario.types";
import { SectionHeading } from "./SectionHeading";

interface ScenarioSetupPreviewProps {
  setupSchema?: SetupInputField[];
}

const optionText = (opt: unknown): string => {
  if (typeof opt === "string") return opt;
  if (opt && typeof opt === "object") {
    const record = opt as { label?: string; value?: string };
    return record.label || record.value || "";
  }
  return "";
};

export const ScenarioSetupPreview: React.FC<ScenarioSetupPreviewProps> = ({
  setupSchema = [],
}) => {
  if (!setupSchema || setupSchema.length === 0) {
    return (
      <section>
        <SectionHeading label="Before you start" />
        <p className="font-sans text-sm text-content-faint">
          Standard character setup. Your choices are assigned when the
          playthrough begins.
        </p>
      </section>
    );
  }

  return (
    <section>
      <SectionHeading
        label="Before you start"
        trailing={
          <span className="font-mono text-xs text-content-faint">
            {setupSchema.length} question
            {setupSchema.length > 1 ? "s" : ""}
          </span>
        }
      />

      <dl className="divide-y divide-border-subtle">
        {setupSchema.map((field, idx) => (
          <div key={field.id || idx} className="py-4 first:pt-0">
            <dt className="flex items-center gap-2">
              <span className="font-sans text-sm font-medium text-content">
                {field.label}
              </span>
              <span className="rounded-full bg-surface px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-content-faint">
                {field.type}
              </span>
            </dt>
            {field.description && (
              <dd className="mt-1 font-sans text-sm text-content-muted">
                {field.description}
              </dd>
            )}
            {field.options && field.options.length > 0 && (
              <dd className="mt-2 flex flex-wrap gap-1.5">
                {field.options.slice(0, 5).map((opt, optIdx) => (
                  <span
                    key={optIdx}
                    className="rounded-full border border-border-subtle bg-surface px-2.5 py-0.5 font-sans text-xs text-content-muted"
                  >
                    {optionText(opt)}
                  </span>
                ))}
                {field.options.length > 5 && (
                  <span className="py-0.5 font-mono text-xs text-content-faint">
                    +{field.options.length - 5}
                  </span>
                )}
              </dd>
            )}
          </div>
        ))}
      </dl>
    </section>
  );
};
