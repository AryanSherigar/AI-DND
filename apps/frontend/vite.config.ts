import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
// Env lives in the monorepo-root .env (single source of truth shared with
// docker-compose). Only VITE_-prefixed keys are exposed to the client bundle.
const MONOREPO_ROOT = path.resolve(__dirname, "../..");

export default defineConfig({
  plugins: [react()],
  envDir: MONOREPO_ROOT,
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    host: true,
  },
});
