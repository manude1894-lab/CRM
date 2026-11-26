import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

export default defineConfig({
  plugins: [react()],
  // The version shown under the sign-in form.
  define: { __APP_VERSION__: JSON.stringify(version) },
  server: { host: "0.0.0.0", port: 3000 },
  preview: { host: "0.0.0.0", port: 3000 },
  // Unit-test coverage of the logic modules (review 22-11-2026, package 6). Screens are covered by the browser
  // tests in e2e/; `npm run coverage` fails if the logic coverage drops under the floor.
  test: {
    coverage: {
      provider: "v8",
      include: ["src/utils/**", "src/hooks/**"],
      exclude: ["**/*.test.js"],
      reporter: ["text-summary", "html"],
      thresholds: { lines: 80, branches: 80 },
    },
  },
});
