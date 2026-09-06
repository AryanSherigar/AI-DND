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
      <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
        Content Tag *
      </label>
      <p className="text-xs text-content-faint">
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
              className={`rounded-md px-3 py-1 text-xs font-mono border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                isSelected
                  ? "bg-content text-surface border-content font-semibold"
                  : "bg-surface-inset text-content-muted border-border-subtle hover:border-border-strong hover:text-content"
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
