import React from "react";
import { SetupInputField } from "@/features/studio/stores/studio.store";

interface ScenarioSetupPreviewProps {
  setupSchema?: SetupInputField[];
}

export const ScenarioSetupPreview: React.FC<ScenarioSetupPreviewProps> = ({
  setupSchema = [],
}) => {
  if (!setupSchema || setupSchema.length === 0) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 md:p-8 shadow-xl space-y-4">
        <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
          <span className="text-xl">⚙️</span>
          <h2 className="font-fell-sc text-2xl font-bold text-amber-200/90">
            Setup Preview
          </h2>
        </div>
        <p className="text-sm font-mono text-zinc-400">
          Standard character setup schema. Custom choices are assigned
          dynamically at start.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 md:p-8 shadow-xl space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">⚙️</span>
          <h2 className="font-fell-sc text-2xl font-bold text-amber-200/90">
            Setup Options Preview
          </h2>
        </div>
        <span className="font-mono text-xs text-zinc-400 bg-zinc-950 border border-zinc-800 px-2.5 py-1 rounded-md">
          {setupSchema.length} Input Field{setupSchema.length > 1 ? "s" : ""}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
        {setupSchema.map((field, idx) => (
          <div
            key={field.id || idx}
            className="rounded-xl border border-zinc-800/80 bg-zinc-950/70 p-4 space-y-1.5"
          >
            <div className="flex items-center justify-between font-mono text-xs">
              <span className="font-bold text-zinc-200">{field.label}</span>
              <span className="text-amber-400/80 bg-amber-500/10 px-2 py-0.5 rounded uppercase">
                {field.type}
              </span>
            </div>
            {field.description && (
              <p className="text-xs text-zinc-400 leading-snug">
                {field.description}
              </p>
            )}
            {field.options && field.options.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {field.options.slice(0, 4).map((opt, optIdx) => {
                  const optText =
                    typeof opt === "string" ? opt : opt.label || opt.value;
                  return (
                    <span
                      key={optIdx}
                      className="text-[11px] font-mono text-zinc-300 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded"
                    >
                      {optText}
                    </span>
                  );
                })}
                {field.options.length > 4 && (
                  <span className="text-[11px] font-mono text-zinc-500 py-0.5">
                    +{field.options.length - 4} more
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
