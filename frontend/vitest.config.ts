import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  esbuild: { jsx: "automatic" },
  // Bound parallelism and avoid Windows child-process termination failures.
  test: { environment: "jsdom", setupFiles: ["./tests/setup.ts"], restoreMocks: true, pool: "threads", maxWorkers: 2 },
});
