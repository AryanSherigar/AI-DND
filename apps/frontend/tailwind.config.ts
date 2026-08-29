import type { Config } from 'tailwindcss'

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        retro: ['"Press Start 2P"', 'monospace'],
        playfair: ['"Playfair Display"', 'serif'],
        vt323: ['"VT323"', 'monospace'],
        pixelify: ['"Pixelify Sans"', 'sans-serif'],
        manrope: ['"Manrope"', 'sans-serif'],
      },
      colors: {
        background: '#0d0f14',
      }
    },
  },
  plugins: [],
} satisfies Config
