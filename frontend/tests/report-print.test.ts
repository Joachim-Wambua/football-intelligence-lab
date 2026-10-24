// @vitest-environment node
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

it("prints a light report in either theme, hides controls and avoids clipped tables", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const print = css.slice(css.indexOf("@media print"));
  expect(print).toContain(":root, .dark");
  expect(print).toContain("--background: #ffffff");
  expect(print).toContain("--foreground: #111111");
  expect(print).toContain(".app-shell > aside, .app-shell > a, .report-controls { display: none !important; }");
  expect(print).toContain("white-space: normal");
  expect(print).toContain("overflow: visible");
  expect(print).toContain("table-header-group");
  expect(print).toContain("break-inside: avoid");
});
