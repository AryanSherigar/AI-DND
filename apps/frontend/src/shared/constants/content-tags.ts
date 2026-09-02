export const CONTENT_TAGS = ["all-ages", "teen", "mature"] as const;

export type ContentTag = (typeof CONTENT_TAGS)[number];

export const CONTENT_TAG_LABELS: Record<ContentTag, string> = {
  "all-ages": "All Ages",
  teen: "Teen",
  mature: "Mature",
};
