// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require("eslint/config");
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  {
    // `schema.d.ts` is generated and `tokens.ts` is generated: neither is edited or linted.
    ignores: ["dist/*", ".expo/*", "src/api/schema.d.ts", "src/theme/tokens.ts"],
  },
  {
    // `jest.mock` factories run before the file's own imports exist, so they `require` (see
    // `src/test/mocks.ts`).
    files: ["src/test/**"],
    rules: { "@typescript-eslint/no-require-imports": "off" },
  },
]);
