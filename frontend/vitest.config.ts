import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
    // jsdom + user-event over react-hook-form can be slow when the file
    // runs after other heavy test files; keep headroom.
    testTimeout: 15_000,
    hookTimeout: 15_000,
  },
});
