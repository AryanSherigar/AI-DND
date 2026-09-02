import React from "react";
import {
  CONTENT_TAGS,
  CONTENT_TAG_LABELS,
  ContentTag,
} from "@/shared/constants/content-tags";

export interface ContentTagPickerProps {
  value: string | null;
  onChange: (tag: ContentTag) => void;
  disabled?: boolean;
}

export const ContentTagPicker: React.FC<ContentTagPickerProps> = ({
  value,
  onChange,
  disabled,
}) => {
  return (
    <div className="space-y-3">
      <label className="block text-sm font-semibold tracking-wide text-zinc-300 uppercase">
        Content Tag *
      </label>
      <p className="text-xs text-zinc-500">
        Declare the content level for this scenario. Checked at publish time.
      </p>
      <div className="flex flex-wrap gap-2">
        {CONTENT_TAGS.map((tag) => {
          const isSelected = value === tag;
          return (
            <button
              key={tag}
              type="button"
              disabled={disabled}
              onClick={() => onChange(tag)}
              className={`px-3 py-1 text-xs font-mono border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                isSelected
                  ? "bg-zinc-100 text-zinc-950 border-zinc-100 font-semibold"
                  : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-600 hover:text-zinc-200"
              }`}
            >
              {CONTENT_TAG_LABELS[tag]}
            </button>
          );
        })}
      </div>
    </div>
  );
};
