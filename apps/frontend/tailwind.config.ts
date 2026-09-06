import type { Config } from "tailwindcss";

/**
 * Semantic design tokens. Values live as space-separated RGB channels in
 * `:root` (src/index.css) so `text-content/70` style opacity modifiers work.
 */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Geist",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
        display: [
          "Outfit",
          "Geist",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
      colors: {
        background: "#0d0f14",
        surface: {
          DEFAULT: token("surface"),
          sunken: token("surface-sunken"),
          raised: token("surface-raised"),
          overlay: token("surface-overlay"),
          inset: token("surface-inset"),
        },
        border: {
          subtle: token("border-subtle"),
          strong: token("border-strong"),
        },
        content: {
          DEFAULT: token("content"),
          muted: token("content-muted"),
          faint: token("content-faint"),
        },
        accent: {
          DEFAULT: token("accent"),
          strong: token("accent-strong"),
          subtle: token("accent-subtle"),
          contrast: token("accent-contrast"),
        },
        success: token("success"),
        danger: token("danger"),
        warning: token("warning"),
      },
      borderRadius: {
        DEFAULT: "0.625rem",
        sm: "0.375rem",
        md: "0.625rem",
        lg: "0.875rem",
        xl: "1.25rem",
        "2xl": "1.5rem",
      },
      boxShadow: {
        elevated:
          "0 1px 2px rgb(0 0 0 / 0.35), 0 12px 32px -12px rgb(0 0 0 / 0.55)",
        "accent-glow": "0 0 0 1px rgb(var(--accent) / 0.35), 0 8px 28px -8px rgb(var(--accent) / 0.35)",
      },
      animation: {
        "aurora-spin": "aurora-spin 6s linear infinite",
      },
      keyframes: {
        "aurora-spin": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
