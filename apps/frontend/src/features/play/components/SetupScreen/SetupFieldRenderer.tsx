import React from "react";
import { NormalizedSetupField } from "./SetupStageCard.types";
import { getStringValue, getArrayValue } from "./setupStageUtils";

interface SetupFieldRendererProps {
  field: NormalizedSetupField;
  value: unknown;
  error?: string;
  onChange: (fieldKey: string, value: unknown) => void;
  onMultiSelectToggle: (fieldKey: string, optionValue: string) => void;
}

const FieldLabel: React.FC<{ field: NormalizedSetupField }> = ({ field }) => (
  <label className="block font-mono text-xs uppercase tracking-wider text-zinc-300 font-semibold group-focus-within:text-amber-400 transition-colors">
    {field.label}{" "}
    {field.is_character_name && (
      <span className="text-[10px] text-amber-500/80 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 ml-1">
        PROTAGONIST
      </span>
    )}
    {field.required && <span className="text-amber-500 font-bold ml-1">*</span>}
  </label>
);

const SelectInput: React.FC<{
  field: NormalizedSetupField;
  value: unknown;
  onChange: (value: string) => void;
}> = ({ field, value, onChange }) => (
  <div className="relative">
    <select
      value={getStringValue(value)}
      onChange={(e) => onChange(e.target.value)}
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
);

const MultiSelectInput: React.FC<{
  field: NormalizedSetupField;
  value: unknown;
  onToggle: (optionValue: string) => void;
}> = ({ field, value, onToggle }) => (
  <div className="space-y-2 bg-zinc-900/60 border border-zinc-800/80 p-4 rounded-lg">
    {field.options.map((opt) => {
      const isChecked = getArrayValue(value).includes(opt.value);
      return (
        <label
          key={opt.id}
          className="flex items-center gap-3 text-xs font-mono text-zinc-300 cursor-pointer hover:text-zinc-100 transition-colors py-1"
        >
          <input
            type="checkbox"
            checked={isChecked}
            onChange={() => onToggle(opt.value)}
            className="w-4 h-4 rounded border-zinc-700 bg-zinc-950 text-amber-500 focus:ring-amber-500/40 accent-amber-500"
          />
          {opt.label}
        </label>
      );
    })}
  </div>
);

export const SetupFieldRenderer: React.FC<SetupFieldRendererProps> = ({
  field,
  value,
  error,
  onChange,
  onMultiSelectToggle,
}) => {
  const isSelect = field.type === "single_select" || field.type === "select";

  return (
    <div className="space-y-2 group">
      <FieldLabel field={field} />
      {field.description && (
        <p className="font-sans text-xs text-zinc-400">{field.description}</p>
      )}

      {isSelect && (
        <SelectInput
          field={field}
          value={value}
          onChange={(val) => onChange(field.key, val)}
        />
      )}

      {field.type === "multi_select" && (
        <MultiSelectInput
          field={field}
          value={value}
          onToggle={(val) => onMultiSelectToggle(field.key, val)}
        />
      )}

      {field.type === "text" && (
        <input
          type="text"
          value={getStringValue(value)}
          onChange={(e) => onChange(field.key, e.target.value)}
          placeholder={field.placeholder || "Enter text..."}
          className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all"
        />
      )}

      {field.type === "textarea" && (
        <textarea
          rows={3}
          value={getStringValue(value)}
          onChange={(e) => onChange(field.key, e.target.value)}
          placeholder={field.placeholder || "Enter details..."}
          className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all resize-none"
        />
      )}

      {field.type === "number" && (
        <input
          type="number"
          value={getStringValue(value)}
          onChange={(e) =>
            onChange(field.key, e.target.valueAsNumber || e.target.value)
          }
          placeholder={field.placeholder}
          className="w-full bg-zinc-900/90 border border-zinc-800 px-4 py-3 text-sm text-zinc-100 font-mono rounded-lg placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40 transition-all"
        />
      )}

      {error && (
        <p className="font-mono text-xs text-red-400 mt-1 flex items-center gap-1">
          <span>⚠</span> {error}
        </p>
      )}
    </div>
  );
};
