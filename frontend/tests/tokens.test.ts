// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, it, expect } from "vitest";

function luminance(hex: string) {
  const rgb = hex.match(/[a-f\d]{2}/gi)!.map(value => parseInt(value, 16) / 255)
    .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
}
function contrast(a: string, b: string) {
  const values = [luminance(a), luminance(b)].sort((a, b) => b - a);
  return (values[0] + .05) / (values[1] + .05);
}
describe("theme token contrast", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  for (const theme of [":root", ".dark"]) {
    it(`${theme} maintains readable text, accent controls and chart outcomes`, () => {
      const block = css.slice(css.indexOf(`${theme} {`)).split("}")[0];
      const tokens = Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[\da-f]{6})/gi)].map(match => [match[1], match[2]]));
      for (const surface of ["background", "surface", "surface-raised"]) {
        expect(contrast(tokens.foreground, tokens[surface])).toBeGreaterThanOrEqual(4.5);
        expect(contrast(tokens.muted, tokens[surface])).toBeGreaterThanOrEqual(4.5);
      }
      expect(contrast(tokens["accent-foreground"], tokens.accent)).toBeGreaterThanOrEqual(4.5);
      for (const outcome of ["chart-complete", "chart-incomplete"]) {
        expect(contrast(tokens[outcome], tokens.pitch)).toBeGreaterThanOrEqual(4.5);
      }
    });
  }
});
