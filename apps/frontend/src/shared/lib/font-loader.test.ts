import { afterEach, describe, expect, it } from "vitest";
import { loadNarrationFont } from "./font-loader";
import { resolveNarrationFont } from "../constants/narration-fonts";

describe("font-loader", () => {
  afterEach(() => {
    document.querySelectorAll("link[id^='font-stylesheet-']").forEach((el) => {
      el.remove();
    });
  });

  it("injects a Google Font stylesheet link on demand", () => {
    loadNarrationFont("cinzel");
    const link = document.getElementById(
      "font-stylesheet-cinzel",
    ) as HTMLLinkElement | null;
    expect(link).not.toBeNull();
    expect(link?.rel).toBe("stylesheet");
    expect(link?.href).toContain("fonts.googleapis.com");
    expect(link?.href).toContain("Cinzel");
  });

  it("injects CDN link for OpenDyslexic", () => {
    loadNarrationFont("open-dyslexic");
    const link = document.getElementById(
      "font-stylesheet-open-dyslexic",
    ) as HTMLLinkElement | null;
    expect(link).not.toBeNull();
    expect(link?.href).toContain("jsdelivr.net");
  });

  it("resolves legacy alias 'serif' to 'im-fell-english'", () => {
    const resolved = resolveNarrationFont("serif");
    expect(resolved.id).toBe("im-fell-english");
  });

  it("does not inject duplicate link tags for the same font", () => {
    loadNarrationFont("orbitron");
    loadNarrationFont("orbitron");
    const links = document.querySelectorAll(
      "link[id='font-stylesheet-orbitron']",
    );
    expect(links.length).toBe(1);
  });
});
