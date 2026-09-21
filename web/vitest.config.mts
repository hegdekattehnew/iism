import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

/**
 * Component tests for the one directory that had none.
 *
 * Every defect found by hand in Sprint 18 -- seeker buttons inside an
 * organisation, a provider shown "Vacancies", an organisation account walked
 * into the candidate wizard -- was a `.tsx` branch on `tenant_type`. CI ran
 * `tsc`, `eslint` and `next build`, and none of those renders anything: a
 * branch that picks the wrong actor compiles perfectly.
 */
export default defineConfig({
  // The tsconfig says `react-jsx` for Next; esbuild needs telling directly.
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
  },
});
