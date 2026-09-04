import { usePlayStore } from "../../../stores/play.store";
import { EBookTheme } from "../../../types/play.types";

export interface EBookThemeTokens {
  isSepia: boolean;
  /** Header/topbar chrome: background + border + text. */
  headerBg: string;
  /** Drawer/modal panel: background + border + text. */
  panelBg: string;
  /** Nested card inside a panel: background + border. */
  cardBg: string;
  /** Solid primary action button: background + hover + text. */
  primaryButton: string;
  /** Active-tab / accent border color. */
  accentBorder: string;
  /** Status/inline badge pill: background + border + text. */
  badgeBg: string;
  /** De-emphasized secondary text color. */
  mutedText: string;
}

const EBOOK_THEME_TOKENS: Record<EBookTheme, EBookThemeTokens> = {
  "dark-velvet": {
    isSepia: false,
    headerBg: "bg-[#000000]/95 border-zinc-800/80 text-zinc-100",
    panelBg: "bg-[#09090b] border-zinc-800 text-zinc-100",
    cardBg: "bg-zinc-900/70 border-zinc-800/80",
    primaryButton: "bg-zinc-100 hover:bg-white text-zinc-950",
    accentBorder: "border-zinc-200",
    badgeBg: "bg-zinc-900/80 border-zinc-700 text-zinc-200",
    mutedText: "text-zinc-400",
  },
  "antique-sepia": {
    isSepia: true,
    headerBg: "bg-[#faf4e8]/95 border-[#d8c7a8] text-[#2c2217]",
    panelBg: "bg-[#faf4e8] border-[#d8c7a8] text-[#2c2217]",
    cardBg: "bg-[#f5ebd7] border-[#e2d5be]",
    primaryButton: "bg-[#2c2217] hover:bg-[#433523] text-[#faf4e8]",
    accentBorder: "border-[#2c2217]",
    badgeBg: "bg-[#f5ebd7] border-[#d8c7a8] text-[#2c2217]",
    mutedText: "text-[#6b5c45]",
  },
};

export function useEBookThemeTokens(): EBookThemeTokens {
  const theme = usePlayStore((s) => s.ebook_theme);
  return EBOOK_THEME_TOKENS[theme];
}
