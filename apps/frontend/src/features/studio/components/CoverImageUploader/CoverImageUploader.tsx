import React, { useRef, useState } from "react";
import {
  ALLOWED_COVER_IMAGE_ACCEPT,
  ALLOWED_COVER_IMAGE_TYPES,
  MAX_COVER_IMAGE_BYTES,
} from "../../constants/upload";
import { useGenerateCoverImage } from "../../hooks/useGenerateCoverImage";
import { useUploadCoverImage } from "../../hooks/useUploadCoverImage";
import { CoverImageUploaderProps } from "./CoverImageUploader.types";

export const CoverImageUploader: React.FC<CoverImageUploaderProps> = ({
  value,
  onChange,
  label,
  description,
  disabled = false,
  className = "",
  generatePrompt = null,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadCoverImage = useUploadCoverImage();
  const generateCoverImage = useGenerateCoverImage();
  const isBusy = uploadCoverImage.isPending || generateCoverImage.isPending;

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_COVER_IMAGE_TYPES.includes(file.type)) {
      return "Unsupported image format. Use JPEG, PNG, or WebP.";
    }
    if (file.size > MAX_COVER_IMAGE_BYTES) {
      return "Image exceeds the 5MB size limit.";
    }
    return null;
  };

  const handleFileProcess = (file: File): void => {
    if (disabled || isBusy) return;
    setErrorMessage(null);
    const validationError = validateFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }
    uploadCoverImage.mutate(file, {
      onSuccess: (data) => onChange(data.url),
      onError: () => setErrorMessage("Upload failed — please try again."),
    });
  };

  const handleGenerateClick = (): void => {
    if (disabled || isBusy || !generatePrompt) return;
    setErrorMessage(null);
    generateCoverImage.mutate(
      {
        title: generatePrompt.title,
        genre_tags: generatePrompt.genreTags,
        opening_scene: generatePrompt.openingScene,
      },
      {
        onSuccess: (data) => onChange(data.url),
        onError: () =>
          setErrorMessage("Image generation failed — please try again."),
      },
    );
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0];
    if (file) handleFileProcess(file);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFileProcess(file);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = (): void => {
    setIsDragging(false);
  };

  const handleRemove = (): void => {
    onChange(null);
    setErrorMessage(null);
  };

  const handleBoxClick = (): void => {
    if (!disabled && !isBusy) {
      fileInputRef.current?.click();
    }
  };

  return (
    <div className={`space-y-3 ${className}`}>
      {label && (
        <label className="block text-sm font-semibold tracking-wide text-content-muted uppercase">
          {label}
        </label>
      )}
      {description && (
        <p className="text-xs text-content-faint">{description}</p>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_COVER_IMAGE_ACCEPT}
        onChange={handleInputChange}
        disabled={disabled || isBusy}
        className="hidden"
        aria-label={label || "Upload cover image"}
      />

      {value ? (
        <div className="relative rounded-lg border border-border-subtle group overflow-hidden">
          <img
            src={value}
            alt="Scenario cover preview"
            className="w-full h-44 object-cover"
          />
          <div className="absolute top-2 right-2 flex gap-2">
            {generatePrompt && (
              <button
                type="button"
                onClick={handleGenerateClick}
                disabled={disabled || isBusy}
                className="rounded-md px-3 py-1.5 bg-surface/80 text-content text-xs font-semibold uppercase tracking-wide border border-border-strong hover:bg-surface-overlay transition-colors disabled:opacity-50"
              >
                {generateCoverImage.isPending
                  ? "Generating…"
                  : "Regenerate with AI"}
              </button>
            )}
            <button
              type="button"
              onClick={handleRemove}
              disabled={disabled}
              className="rounded-md px-3 py-1.5 bg-surface/80 text-content text-xs font-semibold uppercase tracking-wide border border-border-strong hover:bg-surface-overlay transition-colors disabled:opacity-50"
            >
              Remove image
            </button>
          </div>
        </div>
      ) : (
        <div
          onClick={handleBoxClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") handleBoxClick();
          }}
          className={`w-full h-36 flex flex-col items-center justify-center gap-2 border rounded-lg cursor-pointer transition-colors font-sans text-sm ${
            disabled
              ? "opacity-50 cursor-not-allowed border-border-subtle bg-surface-inset"
              : isDragging
                ? "border-accent/50 bg-surface-overlay"
                : "border-border-subtle bg-surface-inset hover:border-border-strong"
          }`}
        >
          {isBusy ? (
            <div className="flex items-center gap-2 text-content-muted">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-content-muted border-t-transparent" />
              <span>
                {generateCoverImage.isPending
                  ? "Generating image…"
                  : "Uploading image…"}
              </span>
            </div>
          ) : (
            <>
              <span className="text-content-muted">
                Click to upload or drag an image here
              </span>
              <span className="text-content-faint text-xs">
                JPEG, PNG, or WebP — up to 5MB
              </span>
            </>
          )}
        </div>
      )}

      {!value && generatePrompt && (
        <button
          type="button"
          onClick={handleGenerateClick}
          disabled={disabled || isBusy}
          className="w-full rounded-lg px-3 py-2 bg-surface-inset text-content-muted text-xs font-semibold uppercase tracking-wide border border-border-subtle hover:border-border-strong transition-colors disabled:opacity-50"
        >
          {generateCoverImage.isPending ? "Generating…" : "Generate with AI"}
        </button>
      )}

      {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
    </div>
  );
};
