export const REPLIT_TEST_CONNECTION_TIMEOUT_MS = 10000;

export const MINIGAME_TYPE_OPTIONS = [
  { value: "dodge", label: "Curated: Dodge Challenge" },
  { value: "replit_embed", label: "Custom: Replit Embed" },
] as const;

export const OUTCOME_MODE_OPTIONS = [
  { value: "binary", label: "Binary (win / lose)" },
  { value: "tiered", label: "Tiered (score ranges)" },
] as const;
