import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    env: {
      VITE_FIREBASE_API_KEY: "test-firebase-api-key",
      VITE_FIREBASE_AUTH_DOMAIN: "test.firebaseapp.com",
      VITE_FIREBASE_PROJECT_ID: "test-project",
      VITE_FIREBASE_STORAGE_BUCKET: "test.appspot.com",
      VITE_FIREBASE_MESSAGING_SENDER_ID: "0",
      VITE_FIREBASE_APP_ID: "test-app-id",
    },
  },
});
