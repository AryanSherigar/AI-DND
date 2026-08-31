import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        fell: ['"IM Fell English"', "serif"],
        "fell-sc": ['"IM Fell English SC"', "serif"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
      colors: {
        background: "#0d0f14",
      },
    },
  },
  plugins: [],
} satisfies Config;
