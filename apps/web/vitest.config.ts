import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

/** Unit tests for the pure logic in `src/lib` — error classification, retry/backoff
 * policy, polling control flow and the constants that must stay in sync with Python.
 *
 * Deliberately scoped to `src/**` and excludes `e2e/`, which is Playwright's. Those two
 * runners both collect `*.spec.ts` and will fight over each other's files otherwise.
 */
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
