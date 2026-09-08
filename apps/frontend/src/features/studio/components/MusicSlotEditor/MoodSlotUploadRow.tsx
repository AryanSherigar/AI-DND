import React, { useRef } from "react";
import { Button } from "@/shared/components/ui/Button";

interface MoodSlotUploadRowProps {
  label: string;
  isBusy: boolean;
  isUploading: boolean;
  isCustomTrack: boolean;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onUseDefault: () => void;
}

export const MoodSlotUploadRow: React.FC<MoodSlotUploadRowProps> = ({
  label,
  isBusy,
  isUploading,
  isCustomTrack,
  onFileSelect,
  onUseDefault,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-wrap gap-2">
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/mpeg,audio/wav,audio/x-wav,audio/ogg"
        onChange={onFileSelect}
        disabled={isBusy}
        className="hidden"
        aria-label={`Upload track for ${label}`}
      />
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={isBusy}
        onClick={() => fileInputRef.current?.click()}
      >
        {isUploading ? "Uploading…" : "Upload track"}
      </Button>
      {isCustomTrack && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={isBusy}
          onClick={onUseDefault}
        >
          Use default
        </Button>
      )}
    </div>
  );
};
