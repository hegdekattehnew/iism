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
  // No JSX option, deliberately. Under vitest 3 the tsconfig's `react-jsx` had to be
  // repeated for esbuild (`esbuild: { jsx: "automatic" }`); vitest 5 runs on vite 8's
  // oxc transform, which reads the tsconfig itself, and that old option is now a type
  // error. Checked rather than assumed: with an explicit `oxc.jsx` setting removed,
  // all 371 tests still pass, so keeping one would only be a second copy to drift.
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
  },
});
