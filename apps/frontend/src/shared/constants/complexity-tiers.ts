export const COMPLEXITY_TIERS = ["newbie", "intermediate", "master"] as const;

export type ComplexityTier = (typeof COMPLEXITY_TIERS)[number];

export const COMPLEXITY_TIER_LABELS: Record<ComplexityTier, string> = {
  newbie: "Newbie",
  intermediate: "Intermediate",
  master: "Master",
};
