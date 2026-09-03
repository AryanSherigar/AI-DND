export const NARRATION_FONTS = [
  "serif",
  "sans-serif",
  "monospace",
  "dyslexic-friendly",
] as const;

export type NarrationFont = (typeof NARRATION_FONTS)[number];

export const NARRATION_FONT_LABELS: Record<NarrationFont, string> = {
  serif: "Serif",
  "sans-serif": "Sans-Serif",
  monospace: "Monospace",
  "dyslexic-friendly": "Dyslexic-Friendly",
};
