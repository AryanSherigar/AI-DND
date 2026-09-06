export type FontGenreCategory =
  | "Fantasy & Medieval"
  | "Literary & Classic"
  | "Sci-Fi & Terminal"
  | "Noir & Detective"
  | "Horror & Gothic"
  | "Modern Clean"
  | "Accessibility";

export interface NarrationFontDefinition {
  id: string;
  label: string;
  category: FontGenreCategory;
  fontFamily: string;
  fontClass: string;
  googleFontFamily?: string;
  cdnUrl?: string;
}

export const FONT_GENRE_CATEGORIES: FontGenreCategory[] = [
  "Fantasy & Medieval",
  "Literary & Classic",
  "Sci-Fi & Terminal",
  "Noir & Detective",
  "Horror & Gothic",
  "Modern Clean",
  "Accessibility",
];

export const NARRATION_FONTS_CATALOG: NarrationFontDefinition[] = [
  // Fantasy & Medieval
  {
    id: "im-fell-english",
    label: "IM Fell English",
    category: "Fantasy & Medieval",
    fontFamily: '"IM Fell English", Georgia, serif',
    fontClass: "font-narration-im-fell-english",
    googleFontFamily: "IM+Fell+English:ital@0;1",
  },
  {
    id: "cinzel",
    label: "Cinzel",
    category: "Fantasy & Medieval",
    fontFamily: '"Cinzel", Georgia, serif',
    fontClass: "font-narration-cinzel",
    googleFontFamily: "Cinzel:wght@400;600;700",
  },
  {
    id: "medieval-sharp",
    label: "MedievalSharp",
    category: "Fantasy & Medieval",
    fontFamily: '"MedievalSharp", cursive, serif',
    fontClass: "font-narration-medieval-sharp",
    googleFontFamily: "MedievalSharp",
  },
  // Literary & Classic
  {
    id: "eb-garamond",
    label: "EB Garamond",
    category: "Literary & Classic",
    fontFamily: '"EB Garamond", Garamond, Georgia, serif',
    fontClass: "font-narration-eb-garamond",
    googleFontFamily: "EB+Garamond:ital,wght@0,400;0,600;1,400",
  },
  {
    id: "merriweather",
    label: "Merriweather",
    category: "Literary & Classic",
    fontFamily: '"Merriweather", Georgia, serif',
    fontClass: "font-narration-merriweather",
    googleFontFamily: "Merriweather:ital,wght@0,300;0,400;1,300",
  },
  // Sci-Fi & Terminal
  {
    id: "ibm-plex-mono",
    label: "IBM Plex Mono",
    category: "Sci-Fi & Terminal",
    fontFamily: '"IBM Plex Mono", monospace',
    fontClass: "font-narration-ibm-plex-mono",
    googleFontFamily: "IBM+Plex+Mono:ital,wght@0,400;0,500;1,400",
  },
  {
    id: "orbitron",
    label: "Orbitron",
    category: "Sci-Fi & Terminal",
    fontFamily: '"Orbitron", sans-serif',
    fontClass: "font-narration-orbitron",
    googleFontFamily: "Orbitron:wght@400;600",
  },
  {
    id: "share-tech-mono",
    label: "Share Tech Mono",
    category: "Sci-Fi & Terminal",
    fontFamily: '"Share Tech Mono", monospace',
    fontClass: "font-narration-share-tech-mono",
    googleFontFamily: "Share+Tech+Mono",
  },
  // Noir & Detective
  {
    id: "special-elite",
    label: "Special Elite",
    category: "Noir & Detective",
    fontFamily: '"Special Elite", "Courier New", monospace',
    fontClass: "font-narration-special-elite",
    googleFontFamily: "Special+Elite",
  },
  {
    id: "courier-prime",
    label: "Courier Prime",
    category: "Noir & Detective",
    fontFamily: '"Courier Prime", Courier, monospace',
    fontClass: "font-narration-courier-prime",
    googleFontFamily: "Courier+Prime:ital,wght@0,400;1,400",
  },
  // Horror & Gothic
  {
    id: "almendra",
    label: "Almendra",
    category: "Horror & Gothic",
    fontFamily: '"Almendra", Georgia, serif',
    fontClass: "font-narration-almendra",
    googleFontFamily: "Almendra:ital,wght@0,400;1,400",
  },
  // Modern Clean
  {
    id: "inter",
    label: "Inter",
    category: "Modern Clean",
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
    fontClass: "font-narration-inter",
    googleFontFamily: "Inter:wght@400;500",
  },
  // Accessibility
  {
    id: "open-dyslexic",
    label: "OpenDyslexic",
    category: "Accessibility",
    fontFamily: '"OpenDyslexic", sans-serif',
    fontClass: "font-narration-open-dyslexic",
    cdnUrl:
      "https://cdn.jsdelivr.net/npm/opendyslexic@1.0.3/open-dyslexic.min.css",
  },
];

export const DEFAULT_NARRATION_FONT_ID = "im-fell-english";
export const READER_FONT_STORAGE_KEY = "ai_dnd_reader_font_override";

export const FONT_ALIASES: Record<string, string> = {
  serif: "im-fell-english",
  "sans-serif": "inter",
  monospace: "ibm-plex-mono",
  "dyslexic-friendly": "open-dyslexic",
};

export const NARRATION_FONTS = [
  ...NARRATION_FONTS_CATALOG.map((f) => f.id),
  "serif",
  "sans-serif",
  "monospace",
  "dyslexic-friendly",
] as const;

export type NarrationFont = (typeof NARRATION_FONTS)[number];

const CATALOG_BY_ID = new Map<string, NarrationFontDefinition>(
  NARRATION_FONTS_CATALOG.map((f) => [f.id, f]),
);

export const resolveNarrationFont = (
  id?: string | null,
): NarrationFontDefinition => {
  if (!id) {
    return CATALOG_BY_ID.get(DEFAULT_NARRATION_FONT_ID)!;
  }
  const canonicalId = FONT_ALIASES[id] ?? id;
  return (
    CATALOG_BY_ID.get(canonicalId) ??
    CATALOG_BY_ID.get(DEFAULT_NARRATION_FONT_ID)!
  );
};

export const NARRATION_FONT_LABELS: Record<string, string> =
  NARRATION_FONTS_CATALOG.reduce<Record<string, string>>(
    (acc, font) => {
      acc[font.id] = font.label;
      return acc;
    },
    {
      serif: "IM Fell English (Default)",
      "sans-serif": "Inter",
      monospace: "IBM Plex Mono",
      "dyslexic-friendly": "OpenDyslexic",
    },
  );
