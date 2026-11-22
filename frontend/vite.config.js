import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
