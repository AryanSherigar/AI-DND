import {
  NarrationFontDefinition,
  resolveNarrationFont,
} from "../constants/narration-fonts";

const LOADED_FONT_IDS = new Set<string>();

function buildGoogleFontUrl(googleFamily: string): string {
  return `https://fonts.googleapis.com/css2?family=${googleFamily}&display=swap`;
}

function createStylesheetLink(id: string, href: string): HTMLLinkElement {
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = href;
  return link;
}

function injectFontStylesheet(definition: NarrationFontDefinition): void {
  const elementId = `font-stylesheet-${definition.id}`;
  if (document.getElementById(elementId)) {
    LOADED_FONT_IDS.add(definition.id);
    return;
  }

  let href: string | null = null;
  if (definition.cdnUrl) {
    href = definition.cdnUrl;
  } else if (definition.googleFontFamily) {
    href = buildGoogleFontUrl(definition.googleFontFamily);
  }

  if (!href) return;

  const link = createStylesheetLink(elementId, href);
  document.head.appendChild(link);
  LOADED_FONT_IDS.add(definition.id);
}

export function loadNarrationFont(fontId?: string | null): void {
  if (typeof document === "undefined") return;

  const definition = resolveNarrationFont(fontId);
  if (LOADED_FONT_IDS.has(definition.id)) return;

  injectFontStylesheet(definition);
}
